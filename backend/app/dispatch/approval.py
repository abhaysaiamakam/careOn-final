"""
CareOn Milestone 5 — Dispatcher Approval & Override Workflow.

Enforces:
- AI-assisted decisions with human dispatcher authority
- Mandatory override reason when selecting a non-recommended candidate
- Atomic double-assignment prevention via conditional SQL updates & partial unique indexes
- Full auditability: records every decision to dispatch_decisions table
- Publishes M4 real-time events in the same database transaction
"""

import json
import uuid
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    Incident,
    Resource,
    Assignment,
    IncidentUpdate,
    Notification,
    DispatchDecision,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_incident_channel,
    get_global_channel,
    get_responder_channel,
)
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.dispatch.approval")


def process_dispatch_decision(
    db: Session,
    incident_id: int,
    selected_resource_id: int,
    dispatcher_id: int,
    dispatcher_name: str,
    decision_type: str,  # "approved" or "overridden"
    override_reason: Optional[str] = None,
    recommended_resource_id: Optional[int] = None,
    candidates_data: Optional[List[Dict[str, Any]]] = None,
    eta_minutes: Optional[float] = None,
    eta_source: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomic execution of a human dispatcher's approval or override decision.
    Guarantees conflict prevention, audit logging, and real-time event publication.
    """
    # 1. Validate mandatory override reason
    if decision_type == "overridden":
        if not override_reason or len(override_reason.strip()) < 5:
            raise ValueError("Mandatory override reason (min 5 characters) is required when overriding a recommendation.")

    # 2. Fetch and validate Incident
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError(f"Incident #{incident_id} not found.")

    if incident.status in ("Resolved", "Cancelled", "Rejected"):
        raise ValueError(f"Cannot dispatch resources to an incident with status '{incident.status}'.")

    active_inc_assignment = (
        db.query(Assignment)
        .filter(Assignment.incident_id == incident.id, Assignment.status == "Active")
        .first()
    )
    if active_inc_assignment:
        raise ValueError(f"Incident {incident.incident_code} already has an active resource assigned.")

    # 3. Fetch and validate Resource
    resource = db.query(Resource).filter(Resource.id == selected_resource_id).first()
    if not resource:
        raise ValueError(f"Resource #{selected_resource_id} not found.")

    # 3b. M6 Safety Invariant: Verify hard safety constraints
    from app.dispatch.assessment import assess_incident
    from app.dispatch.eligibility import check_resource_eligibility
    assessment = assess_incident(incident, db)
    eligibility = check_resource_eligibility(resource, assessment, db)
    if not eligibility.is_eligible:
        raise ValueError(
            f"Resource conflict / safety constraint violation: Selected resource #{selected_resource_id} cannot bypass hard constraints: "
            f"{'; '.join(eligibility.reasons)}"
        )

    if resource.status != "Available":
        # Conflict event publication
        record_and_publish_event(
            db=db,
            event_type="dispatch.assignment_conflict",
            payload={
                "incident_id": incident.id,
                "incident_code": incident.incident_code,
                "resource_id": resource.id,
                "resource_name": resource.name,
                "reason": f"Resource status is '{resource.status}' (not Available).",
            },
            incident_id=incident.id,
            actor_id=dispatcher_id,
            channel=get_global_channel(),
        )
        raise ValueError(f"Resource conflict: {resource.name} is currently {resource.status} and cannot be assigned.")

    # Atomic conditional update on Resource
    rows_claimed = (
        db.query(Resource)
        .filter(Resource.id == selected_resource_id, Resource.status == "Available")
        .update(
            {"status": "Assigned", "current_assignment_id": incident.id, "last_updated": utc_now()},
            synchronize_session=False,
        )
    )
    if rows_claimed == 0:
        raise ValueError(f"Resource conflict: {resource.name} was concurrently claimed by another dispatcher.")

    # 4. Create Active Assignment
    assignment = Assignment(
        incident_id=incident.id,
        resource_id=resource.id,
        assigned_by=dispatcher_name,
        status="Active",
        notes=notes or (
            f"Dispatch {decision_type} by {dispatcher_name}"
            + (f" (Override Reason: {override_reason})" if override_reason else "")
        ),
    )
    db.add(assignment)

    # 5. Update Incident State
    incident.status = "Team Dispatched"
    update_msg = (
        f"Unit {resource.name} ({resource.category}) confirmed and dispatched by {dispatcher_name}."
    )
    if decision_type == "overridden":
        update_msg += f" (Override Reason: {override_reason})"

    db.add(IncidentUpdate(
        incident_id=incident.id,
        status="Team Dispatched",
        message=update_msg,
        actor=dispatcher_name,
    ))

    # 6. User and Dispatch Notifications
    if incident.user_id:
        db.add(Notification(
            user_id=incident.user_id,
            incident_id=incident.id,
            title=f"Emergency Unit Dispatched ({incident.incident_code})",
            message=f"{resource.name} has been assigned to your emergency. Help is on the way.",
            type="info",
        ))

    # 7. Record Immutable Decision to dispatch_decisions
    decision_uuid = str(uuid.uuid4())
    decision_record = DispatchDecision(
        decision_id=decision_uuid,
        incident_id=incident.id,
        recommendation_version=1,
        candidates_json=json.dumps(candidates_data or []),
        recommended_resource_id=recommended_resource_id,
        selected_resource_id=selected_resource_id,
        dispatcher_id=dispatcher_id,
        dispatcher_name=dispatcher_name,
        decision_type=decision_type,
        override_reason=override_reason,
        scoring_weights_version="v1.0",
        eta_minutes=eta_minutes,
        eta_source=eta_source or "calculated",
    )
    db.add(decision_record)
    db.commit()
    db.refresh(assignment)

    # 8. Publish Real-time M4 Events
    event_type = (
        "dispatch.assignment_overridden"
        if decision_type == "overridden"
        else "dispatch.assignment_approved"
    )

    decision_payload = {
        "decision_id": decision_uuid,
        "incident_id": incident.id,
        "incident_code": incident.incident_code,
        "resource_id": resource.id,
        "resource_name": resource.name,
        "resource_code": resource.resource_code,
        "assignment_id": assignment.id,
        "decision_type": decision_type,
        "dispatcher_name": dispatcher_name,
        "override_reason": override_reason,
        "eta_minutes": eta_minutes,
        "timestamp": utc_now().isoformat(),
    }

    # Publish to global dispatch channel & incident channel
    record_and_publish_event(
        db=db,
        event_type=event_type,
        payload=decision_payload,
        incident_id=incident.id,
        actor_id=dispatcher_id,
        channel=get_global_channel(),
    )
    record_and_publish_event(
        db=db,
        event_type=event_type,
        payload=decision_payload,
        incident_id=incident.id,
        actor_id=dispatcher_id,
        channel=get_incident_channel(incident.id),
    )

    # Publish resource availability changed event
    record_and_publish_event(
        db=db,
        event_type="resource.availability_changed",
        payload={
            "resource_id": resource.id,
            "resource_code": resource.resource_code,
            "status": "Assigned",
            "current_incident_id": incident.id,
            "timestamp": utc_now().isoformat(),
        },
        actor_id=dispatcher_id,
        channel=get_global_channel(),
    )

    # If resource has assigned responder user, notify private responder channel
    if resource.assigned_user_id:
        record_and_publish_event(
            db=db,
            event_type="responder.mission_assigned",
            payload={
                "assignment_id": assignment.id,
                "incident_id": incident.id,
                "incident_code": incident.incident_code,
                "category": incident.category,
                "location_name": incident.location_name,
                "latitude": incident.latitude,
                "longitude": incident.longitude,
                "status": "Assigned",
                "notes": assignment.notes,
            },
            incident_id=incident.id,
            actor_id=dispatcher_id,
            channel=get_responder_channel(resource.assigned_user_id),
        )

    return {
        "status": "success",
        "decision_id": decision_uuid,
        "decision_type": decision_type,
        "assignment_id": assignment.id,
        "incident_id": incident.id,
        "resource_id": resource.id,
        "message": f"Resource {resource.name} assigned successfully via dispatcher {decision_type}.",
    }
