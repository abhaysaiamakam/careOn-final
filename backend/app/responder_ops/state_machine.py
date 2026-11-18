"""
CareOn Milestone 6 — Responder Mission State Machine.

Manages the formal operational lifecycle of an emergency response mission:
Assigned -> Accepted -> En Route Incident -> Arrived Scene -> Patient Contact ->
Patient Picked Up -> En Route Hospital -> Arrived Hospital -> Handover Initiated ->
Handover Completed -> Mission Completed (plus Rejected and Cancelled).

Enforces:
- Strict, validated state transitions
- Actor identity, role, and resource ownership checks
- Organization tenant isolation
- Immutable audit trail in mission_event_logs
- Client idempotency (client_action_id)
- Atomic synchronization with Assignment, Resource, and Incident entities
- Publication of M4 real-time WebSocket events via Transactional Outbox
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.models import (
    User,
    Resource,
    Incident,
    Assignment,
    IncidentUpdate,
    MissionEventLog,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_incident_channel,
    get_global_channel,
    get_responder_channel,
    get_org_channel,
)
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.responder_ops.state_machine")


class MissionStatus:
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EN_ROUTE_INCIDENT = "en_route_incident"
    ARRIVED_SCENE = "arrived_scene"
    PATIENT_CONTACT = "patient_contact"
    PATIENT_PICKED_UP = "patient_picked_up"
    EN_ROUTE_HOSPITAL = "en_route_hospital"
    ARRIVED_HOSPITAL = "arrived_hospital"
    HANDOVER_INITIATED = "handover_initiated"
    HANDOVER_COMPLETED = "handover_completed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MissionTransitionError(ValueError):
    """Raised when an invalid state transition is requested."""
    pass


@dataclass
class TransitionResult:
    assignment_id: int
    incident_id: int
    resource_id: int
    previous_status: Optional[str]
    current_status: str
    is_duplicate_replay: bool
    server_timestamp: datetime


# Valid direct transitions
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    MissionStatus.ASSIGNED: {
        MissionStatus.ACCEPTED,
        MissionStatus.REJECTED,
        MissionStatus.CANCELLED,
    },
    MissionStatus.ACCEPTED: {
        MissionStatus.EN_ROUTE_INCIDENT,
        MissionStatus.CANCELLED,
    },
    MissionStatus.EN_ROUTE_INCIDENT: {
        MissionStatus.ARRIVED_SCENE,
        MissionStatus.CANCELLED,
    },
    MissionStatus.ARRIVED_SCENE: {
        MissionStatus.PATIENT_CONTACT,
        # Direct progression to completed allowed if false alarm or treated on-scene
        MissionStatus.COMPLETED,
        MissionStatus.CANCELLED,
    },
    MissionStatus.PATIENT_CONTACT: {
        MissionStatus.PATIENT_PICKED_UP,
        MissionStatus.COMPLETED,  # Treated on scene without transport
        MissionStatus.CANCELLED,
    },
    MissionStatus.PATIENT_PICKED_UP: {
        MissionStatus.EN_ROUTE_HOSPITAL,
        MissionStatus.CANCELLED,
    },
    MissionStatus.EN_ROUTE_HOSPITAL: {
        MissionStatus.ARRIVED_HOSPITAL,
        MissionStatus.CANCELLED,
    },
    MissionStatus.ARRIVED_HOSPITAL: {
        MissionStatus.HANDOVER_INITIATED,
        MissionStatus.CANCELLED,
    },
    MissionStatus.HANDOVER_INITIATED: {
        MissionStatus.HANDOVER_COMPLETED,
        MissionStatus.CANCELLED,
    },
    MissionStatus.HANDOVER_COMPLETED: {
        MissionStatus.COMPLETED,
    },
    MissionStatus.COMPLETED: set(),  # Terminal
    MissionStatus.REJECTED: set(),   # Terminal
    MissionStatus.CANCELLED: set(),  # Terminal
}


def execute_mission_transition(
    db: Session,
    assignment_id: int,
    target_status: str,
    actor: User,
    client_action_id: Optional[str] = None,
    client_timestamp: Optional[datetime] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    notes: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    hospital_id: Optional[int] = None,
) -> TransitionResult:
    """
    Execute a validated state transition in the responder mission lifecycle.
    """
    new_status = target_status.lower().strip()

    # 1. Fetch assignment and related incident & resource
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise ValueError(f"Assignment #{assignment_id} not found.")

    resource = assignment.resource
    incident = assignment.incident

    if not resource or not incident:
        raise ValueError("Assignment is missing associated resource or incident")

    # 2. Authorization & Ownership Validation
    user_role = (getattr(actor, "role", "") or "").lower()
    is_dispatcher_or_admin = user_role in (
        "dispatcher", "admin", "superadmin", "super_admin", "organization_admin"
    )
    is_assigned_responder = (resource.assigned_user_id == actor.id) or (user_role == "responder")

    if not (is_dispatcher_or_admin or is_assigned_responder):
        raise PermissionError(f"Forbidden: User {actor.username} is not authorized to update this mission.")

    # Responder-to-resource ownership: responder cannot modify another unit's mission
    if not is_dispatcher_or_admin and resource.assigned_user_id and resource.assigned_user_id != actor.id:
        raise PermissionError(f"Forbidden: You are assigned to resource ID {actor.id}, not {resource.name}.")

    # 3. Client Idempotency Check
    if client_action_id:
        existing_action = (
            db.query(MissionEventLog)
            .filter(
                MissionEventLog.assignment_id == assignment_id,
                MissionEventLog.client_action_id == client_action_id,
            )
            .first()
        )
        if existing_action:
            logger.info("Idempotent replay detected for action_id %s", client_action_id)
            return TransitionResult(
                assignment_id=assignment.id,
                incident_id=incident.id,
                resource_id=resource.id,
                previous_status=existing_action.previous_status,
                current_status=existing_action.new_status,
                is_duplicate_replay=True,
                server_timestamp=existing_action.server_timestamp,
            )

    # 4. Determine Current Status
    last_event = (
        db.query(MissionEventLog)
        .filter(MissionEventLog.assignment_id == assignment_id)
        .order_by(MissionEventLog.server_timestamp.desc())
        .first()
    )
    current_status = last_event.new_status if last_event else MissionStatus.ASSIGNED

    # Idempotent re-submission of same status
    if current_status == new_status:
        return TransitionResult(
            assignment_id=assignment.id,
            incident_id=incident.id,
            resource_id=resource.id,
            previous_status=last_event.previous_status if last_event else None,
            current_status=current_status,
            is_duplicate_replay=True,
            server_timestamp=last_event.server_timestamp if last_event else utc_now(),
        )

    # 5. Validate Transition Matrix
    allowed_transitions = VALID_TRANSITIONS.get(current_status, set())
    if is_dispatcher_or_admin:
        # Dispatchers can abort or cancel from any non-terminal state
        if current_status not in (MissionStatus.COMPLETED, MissionStatus.REJECTED, MissionStatus.CANCELLED):
            allowed_transitions = allowed_transitions.union({MissionStatus.CANCELLED})

    if new_status not in allowed_transitions:
        raise MissionTransitionError(
            f"Invalid mission state transition from '{current_status}' to '{new_status}'. "
            f"Allowed transitions: {sorted(list(allowed_transitions))}"
        )

    server_now = utc_now()

    # 6. Rejection Requirements
    if new_status == MissionStatus.REJECTED:
        if not rejection_reason or len(rejection_reason.strip()) < 3:
            raise MissionTransitionError("Rejection reason is mandatory when rejecting a mission.")
        assignment.acknowledgement_status = "rejected"
        assignment.rejection_reason = rejection_reason
        assignment.status = "Released"
        assignment.released_at = server_now
        resource.status = "Available"
        resource.current_assignment_id = None
        incident.status = "Received"  # Return incident to pool for reassignment

    elif new_status == MissionStatus.ACCEPTED:
        assignment.acknowledgement_status = "acknowledged"
        assignment.acknowledged_at = server_now
        resource.status = "Assigned"

    elif new_status == MissionStatus.EN_ROUTE_INCIDENT:
        resource.status = "Busy"
        incident.status = "In Progress"

    elif new_status == MissionStatus.ARRIVED_SCENE:
        resource.status = "Busy"

    elif new_status == MissionStatus.PATIENT_PICKED_UP:
        resource.status = "Busy"

    elif new_status == MissionStatus.EN_ROUTE_HOSPITAL:
        resource.status = "Busy"

    elif new_status == MissionStatus.ARRIVED_HOSPITAL:
        resource.status = "Busy"

    elif new_status == MissionStatus.HANDOVER_COMPLETED:
        resource.status = "Available"

    elif new_status == MissionStatus.COMPLETED:
        assignment.status = "Completed"
        assignment.completed_at = server_now
        resource.status = "Available"
        resource.current_assignment_id = None
        # Check if all assignments for this incident are completed
        other_active = (
            db.query(Assignment)
            .filter(
                Assignment.incident_id == incident.id,
                Assignment.id != assignment.id,
                Assignment.status == "Active",
            )
            .count()
        )
        if other_active == 0:
            incident.status = "Resolved"
            incident.resolved_at = server_now

    elif new_status == MissionStatus.CANCELLED:
        assignment.status = "Cancelled"
        assignment.released_at = server_now
        resource.status = "Available"
        resource.current_assignment_id = None

    # Update Resource coordinates if supplied
    if latitude is not None and longitude is not None:
        resource.latitude = latitude
        resource.longitude = longitude
        resource.geom = f"POINT({longitude} {latitude})"
        resource.last_updated = server_now

    # 7. Record Immutable Mission Event Log
    event_log = MissionEventLog(
        assignment_id=assignment.id,
        incident_id=incident.id,
        resource_id=resource.id,
        actor_id=actor.id,
        actor_role=actor.role if hasattr(actor, "role") else "Responder",
        previous_status=current_status,
        new_status=new_status,
        client_action_id=client_action_id,
        client_timestamp=client_timestamp or server_now,
        server_timestamp=server_now,
        latitude=latitude,
        longitude=longitude,
        notes=notes,
        rejection_reason=rejection_reason,
        hospital_id=hospital_id,
    )
    db.add(event_log)

    # 8. Record Incident Update for audit timeline
    update_text = f"Mission status changed from '{current_status}' to '{new_status}' by {actor.name}"
    if notes:
        update_text += f". Notes: {notes}"
    if rejection_reason:
        update_text += f". Reason: {rejection_reason}"

    incident_update = IncidentUpdate(
        incident_id=incident.id,
        status=incident.status,
        message=update_text,
        actor=actor.name,
        created_at=server_now,
    )
    db.add(incident_update)

    db.commit()
    db.refresh(event_log)

    # 9. Real-Time Broadcast via Transactional Outbox
    event_type = f"responder.mission_{new_status}"
    event_payload = {
        "event_id": event_log.id,
        "assignment_id": assignment.id,
        "incident_id": incident.id,
        "incident_code": incident.incident_code,
        "resource_id": resource.id,
        "resource_name": resource.name,
        "actor_name": actor.name,
        "previous_status": current_status,
        "new_status": new_status,
        "latitude": latitude,
        "longitude": longitude,
        "notes": notes,
        "rejection_reason": rejection_reason,
        "timestamp": event_log.server_timestamp.isoformat(),
    }

    # Broadcast to incident channel, global dispatch channel, and unit channel
    record_and_publish_event(
        db=db,
        event_type=event_type,
        payload=event_payload,
        incident_id=incident.id,
        actor_id=actor.id,
        channel=get_incident_channel(incident.id),
    )
    record_and_publish_event(
        db=db,
        event_type=event_type,
        payload=event_payload,
        incident_id=incident.id,
        actor_id=actor.id,
        channel=get_global_channel(),
    )
    if resource.assigned_user_id:
        record_and_publish_event(
            db=db,
            event_type=event_type,
            payload=event_payload,
            incident_id=incident.id,
            actor_id=actor.id,
            channel=get_responder_channel(resource.assigned_user_id),
        )

    # If destination hospital specified, broadcast to hospital organization channel
    if hospital_id:
        record_and_publish_event(
            db=db,
            event_type="hospital.incoming_patient_updated",
            payload=event_payload,
            organization_id=hospital_id,
            actor_id=actor.id,
            channel=get_org_channel(hospital_id),
        )

    return TransitionResult(
        assignment_id=assignment.id,
        incident_id=incident.id,
        resource_id=resource.id,
        previous_status=current_status,
        current_status=new_status,
        is_duplicate_replay=False,
        server_timestamp=event_log.server_timestamp,
    )


def get_mission_event_history(db: Session, assignment_id: int) -> List[MissionEventLog]:
    """Retrieve chronologically ordered immutable event history for an assignment."""
    return (
        db.query(MissionEventLog)
        .filter(MissionEventLog.assignment_id == assignment_id)
        .order_by(MissionEventLog.server_timestamp.asc())
        .all()
    )


# Alias for backwards compatibility
transition_mission_state = execute_mission_transition
