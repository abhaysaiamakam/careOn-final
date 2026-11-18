"""
Inter-Agency Mutual Aid Resource Request Service.
Operational Constraint: Resource requests are NEVER automatic dispatch orders.
The receiving agency retains operational sovereignty to accept, decline, or fulfill.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    Incident,
    Organization,
    User,
    AgencyResourceRequest,
    utc_now,
)
from app.realtime.event_publisher import record_and_publish_event
from app.coordination.collaboration_service import log_inter_agency_audit

VALID_RESOURCE_TYPES = {
    "AMBULANCE",
    "FIRE_TRUCK",
    "HAZMAT_UNIT",
    "POLICE_PATROL",
    "RESCUE_SQUAD",
    "HELICOPTER",
    "WATER_TANKER",
    "OTHER",
}

VALID_URGENCY_LEVELS = {
    "ROUTINE",
    "URGENT",
    "EMERGENCY",
    "LIFE_THREATENING",
}


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_resource_request(
    db: Session,
    incident_id: int,
    requesting_org_id: int,
    requested_org_id: int,
    requested_by_user_id: int,
    resource_type: str,
    quantity: int,
    urgency: str,
    operational_justification: str,
    staging_location_name: Optional[str] = None,
    staging_latitude: Optional[float] = None,
    staging_longitude: Optional[float] = None,
    expires_hours: Optional[int] = 6,
) -> AgencyResourceRequest:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found.")

    target_org = db.query(Organization).filter(Organization.id == requested_org_id).first()
    if not target_org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Requested organization {requested_org_id} not found.")

    res_type = resource_type.upper()
    if res_type not in VALID_RESOURCE_TYPES:
        res_type = "OTHER"

    urg = urgency.upper()
    if urg not in VALID_URGENCY_LEVELS:
        urg = "ROUTINE"

    expires_at = utc_now() + timedelta(hours=expires_hours) if expires_hours else None

    req = AgencyResourceRequest(
        request_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        requesting_organization_id=requesting_org_id,
        requested_organization_id=requested_org_id,
        requested_by_user_id=requested_by_user_id,
        resource_type=res_type,
        quantity=quantity,
        urgency=urg,
        status="REQUESTED",
        operational_justification=operational_justification,
        staging_location_name=staging_location_name,
        staging_latitude=staging_latitude,
        staging_longitude=staging_longitude,
        expires_at=expires_at,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(req)
    db.flush()

    log_inter_agency_audit(
        db=db,
        incident_id=incident_id,
        acting_org_id=requesting_org_id,
        acting_user_id=requested_by_user_id,
        action_type="RESOURCE_REQUESTED",
        target_agency_id=requested_org_id,
        target_resource_type="RESOURCE_REQUEST",
        target_resource_id=req.request_uuid,
        details={
            "resource_type": res_type,
            "quantity": quantity,
            "urgency": urg,
            "justification": operational_justification,
        },
    )

    record_and_publish_event(
        db=db,
        event_type="inter_agency.resource.requested",
        payload={
            "request_uuid": req.request_uuid,
            "incident_id": incident_id,
            "requesting_org_id": requesting_org_id,
            "requested_org_id": requested_org_id,
            "resource_type": res_type,
            "quantity": quantity,
            "urgency": urg,
        },
        organization_id=requested_org_id,
        incident_id=incident_id,
        actor_id=requested_by_user_id,
    )

    db.commit()
    db.refresh(req)
    return req


def action_resource_request(
    db: Session,
    request_id: int,
    acting_org_id: int,
    acting_user_id: int,
    action: str,
    decision_notes: Optional[str] = None,
    assigned_resource_ids: Optional[List[str]] = None,
) -> AgencyResourceRequest:
    req = db.query(AgencyResourceRequest).filter(AgencyResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource request not found.")

    act = action.upper()
    if act not in ("ACKNOWLEDGE", "ACCEPT", "DECLINE", "FULFILL", "CANCEL"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid action: {action}")

    # Check expiration
    if req.expires_at and ensure_utc(req.expires_at) < utc_now() and req.status not in ("FULFILLED", "CANCELLED", "DECLINED"):
        req.status = "EXPIRED"
        req.updated_at = utc_now()
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource request has expired.")

    # Permissions
    is_requested_org = (req.requested_organization_id == acting_org_id)
    is_requesting_org = (req.requesting_organization_id == acting_org_id)

    if act == "CANCEL":
        if not is_requesting_org and not is_requested_org:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to cancel request.")
        req.status = "CANCELLED"
    else:
        if not is_requested_org:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only requested agency can decide on resource requests.")

        if act == "ACKNOWLEDGE":
            req.status = "ACKNOWLEDGED"
        elif act == "ACCEPT":
            req.status = "ACCEPTED"
            if assigned_resource_ids:
                req.assigned_resource_ids_json = json.dumps(assigned_resource_ids)
        elif act == "DECLINE":
            req.status = "DECLINED"
        elif act == "FULFILL":
            req.status = "FULFILLED"
            if assigned_resource_ids:
                req.assigned_resource_ids_json = json.dumps(assigned_resource_ids)

    req.decision_by_user_id = acting_user_id
    req.decision_at = utc_now()
    if decision_notes:
        req.decision_notes = decision_notes
    req.updated_at = utc_now()

    log_inter_agency_audit(
        db=db,
        incident_id=req.incident_id,
        acting_org_id=acting_org_id,
        acting_user_id=acting_user_id,
        action_type=f"RESOURCE_REQUEST_{req.status}",
        target_agency_id=req.requesting_organization_id if is_requested_org else req.requested_organization_id,
        target_resource_type="RESOURCE_REQUEST",
        target_resource_id=req.request_uuid,
        details={"status": req.status, "decision_notes": decision_notes, "resources": assigned_resource_ids},
    )

    record_and_publish_event(
        db=db,
        event_type="inter_agency.resource.decided",
        payload={
            "request_uuid": req.request_uuid,
            "incident_id": req.incident_id,
            "status": req.status,
            "assigned_resources": assigned_resource_ids or [],
        },
        organization_id=req.requesting_organization_id,
        incident_id=req.incident_id,
        actor_id=acting_user_id,
    )

    db.commit()
    db.refresh(req)
    return req
