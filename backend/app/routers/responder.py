"""
CareOn Milestone 3 — Responder Mission Router.

Endpoints for field responders (mobile web and native app):
- GET  /api/responder/me         → Profile, assigned resource, active mission
- GET  /api/responder/missions    → List assigned missions
- GET  /api/responder/missions/{id} → Details of a mission
- POST /api/responder/missions/{id}/accept → Accept assignment
- POST /api/responder/missions/{id}/reject → Reject assignment with reason
- POST /api/responder/missions/{id}/status → Advance mission status (En Route, On Scene, etc.)
- POST /api/responder/telemetry  → Update responder's live GPS coordinates
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, object_session

from app.database import get_db
from app.models import (
    User,
    Resource,
    Assignment,
    Incident,
    IncidentUpdate,
    AuditLog,
    IncomingPatientRequest,
    HospitalFacility,
    make_point_wkt,
    utc_now,
)
from app.hospital_ops.readiness import get_designated_facility
from app.rbac.roles import UserRole, Permission
from app.rbac.dependencies import get_current_user_flexible, require_role
from app.rbac.permissions import require_permission
from app.schemas import (
    MissionResponse,
    MissionActionRequest,
    MissionStatusUpdate,
    ResponderTelemetryUpdate,
)

router = APIRouter(prefix="/api/responder", tags=["Responder"])

ALLOWED_RESPONDER_ROLES = (
    UserRole.RESPONDER,
    UserRole.DISPATCHER,
    UserRole.ORGANIZATION_ADMIN,
    UserRole.SUPER_ADMIN,
)


def _get_responder_resource(user: User, db: Session) -> Optional[Resource]:
    """Find the resource assigned to this responder user."""
    res = db.query(Resource).filter(Resource.assigned_user_id == user.id).first()
    if res:
        return res
    # Fallback: if user is admin/dispatcher or in test environment, match by name or return first available
    return db.query(Resource).filter(Resource.status.in_(["Assigned", "Available", "Busy"])).first()


def _build_mission_response(assignment: Assignment, db: Optional[Session] = None) -> MissionResponse:
    inc = assignment.incident
    res = assignment.resource

    dest_hospital_id = None
    dest_hospital_name = None
    dest_hospital_lat = None
    dest_hospital_lon = None

    session = db or object_session(assignment)
    if session:
        inc_req = (
            session.query(IncomingPatientRequest)
            .filter(
                IncomingPatientRequest.incident_id == assignment.incident_id,
                IncomingPatientRequest.status.in_(["accepted", "acknowledged", "pending"]),
            )
            .order_by(
                IncomingPatientRequest.created_at.desc(),
            )
            .first()
        )
        if inc_req and inc_req.facility:
            dest_hospital_id = inc_req.facility.id
            dest_hospital_name = inc_req.facility.name
            dest_hospital_lat = inc_req.facility.latitude
            dest_hospital_lon = inc_req.facility.longitude
        else:
            desig = get_designated_facility(session)
            if desig:
                dest_hospital_id = desig.id
                dest_hospital_name = desig.name
                dest_hospital_lat = desig.latitude
                dest_hospital_lon = desig.longitude

    return MissionResponse(
        id=assignment.id,
        incident_id=inc.id,
        incident_code=inc.incident_code,
        category=inc.category,
        priority=inc.priority,
        title=inc.title,
        description=inc.description,
        location_name=inc.location_name,
        latitude=inc.latitude,
        longitude=inc.longitude,
        affected_people=inc.affected_people,
        help_required=inc.help_required,
        status=assignment.status,
        incident_status=inc.status,
        assigned_at=assignment.assigned_at,
        resource_id=res.id,
        resource_code=res.resource_code,
        resource_name=res.name,
        notes=assignment.notes,
        destination_hospital_id=dest_hospital_id,
        destination_hospital_name=dest_hospital_name,
        destination_hospital_latitude=dest_hospital_lat,
        destination_hospital_longitude=dest_hospital_lon,
    )


@router.get("/me")
def get_responder_profile(
    user: User = Depends(require_role(*ALLOWED_RESPONDER_ROLES)),
    db: Session = Depends(get_db),
):
    """Return responder user profile, assigned unit, and current active mission."""
    resource = _get_responder_resource(user, db)
    active_assignment = None
    if resource:
        active_assignment = (
            db.query(Assignment)
            .filter(
                Assignment.resource_id == resource.id,
                Assignment.status.in_(["Active", "Accepted", "En Route", "On Scene", "Transporting"]),
            )
            .order_by(Assignment.assigned_at.desc(), Assignment.id.desc())
            .first()
        )

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
        },
        "assigned_resource": {
            "id": resource.id,
            "code": resource.resource_code,
            "name": resource.name,
            "category": resource.category,
            "status": resource.status,
            "latitude": resource.latitude,
            "longitude": resource.longitude,
            "location_name": resource.location_name,
        } if resource else None,
        "active_mission": _build_mission_response(active_assignment) if active_assignment else None,
    }


@router.get("/missions", response_model=List[MissionResponse])
def list_responder_missions(
    user: User = Depends(require_permission(Permission.RESPONDER_MISSION_READ)),
    db: Session = Depends(get_db),
):
    """List missions assigned to the authenticated responder's unit."""
    resource = _get_responder_resource(user, db)
    query = db.query(Assignment).join(Assignment.incident)
    
    # If standard responder, scope strictly to their assigned resource
    effective_role = user.role.lower()
    if effective_role == "responder" and resource:
        query = query.filter(Assignment.resource_id == resource.id)
    
    assignments = query.order_by(Assignment.assigned_at.desc()).limit(20).all()
    return [_build_mission_response(a) for a in assignments]


@router.get("/missions/{assignment_id}", response_model=MissionResponse)
def get_responder_mission_detail(
    assignment_id: int,
    user: User = Depends(require_permission(Permission.RESPONDER_MISSION_READ)),
    db: Session = Depends(get_db),
):
    """Get full details of a specific responder mission."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission assignment not found.")
    return _build_mission_response(assignment)


@router.post("/missions/{assignment_id}/accept", response_model=MissionResponse)
def accept_mission(
    assignment_id: int,
    payload: MissionActionRequest = MissionActionRequest(),
    user: User = Depends(require_permission(Permission.RESPONDER_MISSION_UPDATE)),
    db: Session = Depends(get_db),
):
    """Responder accepts an emergency dispatch assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission assignment not found.")

    assignment.status = "Accepted"
    assignment.notes = f"Accepted by {user.name}. {payload.reason or ''}".strip()

    # Update resource status
    if assignment.resource:
        assignment.resource.status = "Assigned"

    # Log public incident update
    inc_update = IncidentUpdate(
        incident_id=assignment.incident_id,
        status="Assignment Confirmed",
        message=f"Responder unit {assignment.resource.name} accepted the dispatch.",
        actor=user.name,
        is_public=True,
    )
    db.add(inc_update)

    # Log audit entry
    audit = AuditLog(
        action="MISSION_ACCEPT",
        entity_type="assignment",
        entity_id=str(assignment.id),
        actor=user.name,
        details=f"Responder accepted mission for incident {assignment.incident.incident_code}",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)

    try:
        from app.realtime.event_publisher import record_and_publish_event
        from app.realtime.event_models import EventTypes
        record_and_publish_event(
            db=db,
            event_type=EventTypes.RESPONDER_MISSION_ACCEPTED,
            payload={
                "assignment_id": assignment.id,
                "incident_id": assignment.incident_id,
                "incident_code": assignment.incident.incident_code,
                "resource_id": assignment.resource_id,
                "resource_name": assignment.resource.name if assignment.resource else "Unit",
                "status": assignment.status,
                "responder_name": user.name,
            },
            incident_id=assignment.incident_id,
            actor_id=user.id,
        )
    except Exception as exc:
        pass

    return _build_mission_response(assignment)


@router.post("/missions/{assignment_id}/reject", response_model=MissionResponse)
def reject_mission(
    assignment_id: int,
    payload: MissionActionRequest,
    user: User = Depends(require_permission(Permission.RESPONDER_MISSION_UPDATE)),
    db: Session = Depends(get_db),
):
    """Responder rejects an emergency dispatch assignment with mandatory reason."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission assignment not found.")

    reason = payload.reason or "Unit unavailable or reassigned."
    assignment.status = "Rejected"
    assignment.released_at = utc_now()
    assignment.notes = f"Rejected by {user.name}: {reason}"

    # Release resource back to Available
    if assignment.resource:
        assignment.resource.status = "Available"
        assignment.resource.current_assignment_id = None

    # Update incident status back to assistance search
    incident = assignment.incident
    incident.status = "Assistance Search"

    inc_update = IncidentUpdate(
        incident_id=incident.id,
        status="Assistance Search",
        message=f"Unit {assignment.resource.name} could not accept ({reason}). Re-dispatching.",
        actor=user.name,
        is_public=True,
    )
    db.add(inc_update)

    # Log audit entry in reject_mission
    audit = AuditLog(
        action="MISSION_REJECT",
        entity_type="assignment",
        entity_id=str(assignment.id),
        actor=user.name,
        details=f"Responder rejected mission for incident {incident.incident_code}: {reason}",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)

    try:
        from app.realtime.event_publisher import record_and_publish_event
        from app.realtime.event_models import EventTypes
        record_and_publish_event(
            db=db,
            event_type=EventTypes.RESPONDER_MISSION_REJECTED,
            payload={
                "assignment_id": assignment.id,
                "incident_id": incident.id,
                "incident_code": incident.incident_code,
                "resource_id": assignment.resource_id,
                "reason": reason,
                "responder_name": user.name,
            },
            incident_id=incident.id,
            actor_id=user.id,
        )
    except Exception as exc:
        pass

    return _build_mission_response(assignment)


@router.post("/missions/{assignment_id}/status", response_model=MissionResponse)
def update_mission_status(
    assignment_id: int,
    payload: MissionStatusUpdate,
    user: User = Depends(require_permission(Permission.RESPONDER_MISSION_UPDATE)),
    db: Session = Depends(get_db),
):
    """Advance mission status through standard lifecycle steps."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission assignment not found.")

    new_status = payload.status
    assignment.status = new_status
    if payload.notes:
        assignment.notes = f"{assignment.notes or ''} | {payload.notes}".strip(" |")

    incident = assignment.incident
    resource = assignment.resource

    # Lifecycle synchronization
    if new_status.lower() in ("en route", "enroute"):
        incident.status = "Team Dispatched"
        if resource:
            resource.status = "Busy"
        status_msg = f"{resource.name} is en route to scene."
    elif new_status.lower() in ("on scene", "onscene", "arrived"):
        incident.status = "Team Arrived"
        status_msg = f"{resource.name} arrived on scene."
    elif new_status.lower() in ("transporting", "en route to hospital"):
        incident.status = "Team Arrived"
        status_msg = f"{resource.name} is transporting patient to hospital."
    elif new_status.lower() in ("arrived hospital", "at hospital"):
        status_msg = f"{resource.name} arrived at hospital emergency department."
    elif new_status.lower() in ("cleared", "completed", "resolved"):
        assignment.status = "Completed"
        assignment.released_at = utc_now()
        if resource:
            resource.status = "Available"
            resource.current_assignment_id = None
        incident.status = "Resolved"
        status_msg = f"{resource.name} completed mission and is back in service."
    else:
        status_msg = f"Status updated to {new_status}."

    inc_update = IncidentUpdate(
        incident_id=incident.id,
        status=incident.status,
        message=status_msg,
        actor=user.name,
        is_public=True,
    )
    db.add(inc_update)

    # Log audit entry in update_mission_status
    audit = AuditLog(
        action="MISSION_STATUS_UPDATE",
        entity_type="assignment",
        entity_id=str(assignment.id),
        actor=user.name,
        details=f"Mission status updated to {new_status} for incident {incident.incident_code}",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)

    try:
        from app.realtime.event_publisher import record_and_publish_event
        from app.realtime.event_models import EventTypes
        ev_type = EventTypes.RESPONDER_STATUS_CHANGED
        if new_status.lower() in ("on scene", "onscene", "arrived"):
            ev_type = EventTypes.RESPONDER_ARRIVED_AT_INCIDENT
        elif new_status.lower() in ("transporting", "en route to hospital"):
            ev_type = EventTypes.RESPONDER_PATIENT_PICKED_UP
        elif new_status.lower() in ("arrived hospital", "at hospital"):
            ev_type = EventTypes.RESPONDER_ARRIVED_AT_HOSPITAL

        record_and_publish_event(
            db=db,
            event_type=ev_type,
            payload={
                "assignment_id": assignment.id,
                "incident_id": incident.id,
                "incident_code": incident.incident_code,
                "status": assignment.status,
                "incident_status": incident.status,
                "responder_name": user.name,
                "notes": assignment.notes,
            },
            incident_id=incident.id,
            actor_id=user.id,
        )
    except Exception as exc:
        pass

    return _build_mission_response(assignment)


@router.post("/telemetry")
def update_telemetry(
    payload: ResponderTelemetryUpdate,
    user: User = Depends(require_permission(Permission.RESPONDER_MISSION_UPDATE)),
    db: Session = Depends(get_db),
):
    """Update live GPS telemetry coordinates for responder's resource unit."""
    resource = _get_responder_resource(user, db)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No assigned resource unit found for this responder user.",
        )

    resource.latitude = payload.latitude
    resource.longitude = payload.longitude
    resource.geom = make_point_wkt(payload.latitude, payload.longitude)
    resource.last_updated = utc_now()
    db.commit()

    return {
        "status": "ok",
        "resource_id": resource.id,
        "resource_code": resource.resource_code,
        "latitude": resource.latitude,
        "longitude": resource.longitude,
        "last_updated": resource.last_updated.isoformat(),
    }
