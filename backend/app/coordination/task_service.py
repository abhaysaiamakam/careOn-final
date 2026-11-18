"""
Cross-Agency Operational Task Management Service.
Coordinates operational assignments across responding agencies under unified command.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    Incident,
    Organization,
    User,
    AgencyOperationalTask,
    IncidentCommandStructure,
    utc_now,
)
from app.realtime.event_publisher import record_and_publish_event
from app.coordination.collaboration_service import log_inter_agency_audit

VALID_TASK_STATUSES = {
    "DRAFT",
    "REQUESTED",
    "ACKNOWLEDGED",
    "IN_PROGRESS",
    "BLOCKED",
    "COMPLETED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
}


def create_operational_task(
    db: Session,
    incident_id: int,
    assigning_org_id: int,
    assigned_org_id: int,
    created_by_user_id: int,
    title: str,
    description: str,
    priority: str = "MEDIUM",
    assigned_unit_name: Optional[str] = None,
    deadline: Optional[datetime] = None,
    command_structure_id: Optional[int] = None,
) -> AgencyOperationalTask:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found.")

    assigned_org = db.query(Organization).filter(Organization.id == assigned_org_id).first()
    if not assigned_org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assigned organization {assigned_org_id} not found.")

    prio = priority.upper()
    if prio not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        prio = "MEDIUM"

    task = AgencyOperationalTask(
        task_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        command_structure_id=command_structure_id,
        assigning_organization_id=assigning_org_id,
        assigned_organization_id=assigned_org_id,
        created_by_user_id=created_by_user_id,
        title=title,
        description=description,
        priority=prio,
        status="REQUESTED",
        assigned_unit_name=assigned_unit_name,
        deadline=deadline,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(task)
    db.flush()

    log_inter_agency_audit(
        db=db,
        incident_id=incident_id,
        acting_org_id=assigning_org_id,
        acting_user_id=created_by_user_id,
        action_type="TASK_REQUESTED",
        target_agency_id=assigned_org_id,
        target_resource_type="AGENCY_TASK",
        target_resource_id=task.task_uuid,
        details={"title": title, "priority": prio, "deadline": deadline.isoformat() if deadline else None},
    )

    record_and_publish_event(
        db=db,
        event_type="inter_agency.task.requested",
        payload={
            "task_uuid": task.task_uuid,
            "incident_id": incident_id,
            "assigning_org_id": assigning_org_id,
            "assigned_org_id": assigned_org_id,
            "title": title,
            "priority": prio,
        },
        organization_id=assigned_org_id,
        incident_id=incident_id,
        actor_id=created_by_user_id,
    )

    db.commit()
    db.refresh(task)
    return task


def update_operational_task_status(
    db: Session,
    task_id: int,
    acting_org_id: int,
    acting_user_id: int,
    new_status: Optional[str] = None,
    assigned_unit_name: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    status_notes: Optional[str] = None,
) -> AgencyOperationalTask:
    task = db.query(AgencyOperationalTask).filter(AgencyOperationalTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operational task not found.")

    if new_status:
        status_upper = new_status.upper()
        if status_upper not in VALID_TASK_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid task status: {new_status}")

        task.status = status_upper
        if status_upper == "ACKNOWLEDGED":
            task.acknowledged_at = utc_now()
            task.acknowledged_by_user_id = acting_user_id
        elif status_upper == "COMPLETED":
            task.completed_at = utc_now()
            task.completed_by_user_id = acting_user_id
        elif status_upper == "REJECTED":
            task.rejection_reason = rejection_reason or "Rejected by assigned agency"

    if assigned_unit_name is not None:
        task.assigned_unit_name = assigned_unit_name
    if rejection_reason is not None:
        task.rejection_reason = rejection_reason
    if status_notes is not None:
        task.status_notes = status_notes

    task.updated_at = utc_now()

    log_inter_agency_audit(
        db=db,
        incident_id=task.incident_id,
        acting_org_id=acting_org_id,
        acting_user_id=acting_user_id,
        action_type=f"TASK_STATUS_{task.status}",
        target_agency_id=task.assigning_organization_id if acting_org_id == task.assigned_organization_id else task.assigned_organization_id,
        target_resource_type="AGENCY_TASK",
        target_resource_id=task.task_uuid,
        details={"status": task.status, "status_notes": status_notes, "unit": assigned_unit_name},
    )

    record_and_publish_event(
        db=db,
        event_type="inter_agency.task.updated",
        payload={
            "task_uuid": task.task_uuid,
            "incident_id": task.incident_id,
            "status": task.status,
            "assigned_unit": task.assigned_unit_name,
        },
        organization_id=task.assigning_organization_id,
        incident_id=task.incident_id,
        actor_id=acting_user_id,
    )

    db.commit()
    db.refresh(task)
    return task
