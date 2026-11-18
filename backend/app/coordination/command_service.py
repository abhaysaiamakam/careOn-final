"""
Incident Command System (ICS) Service.
Enforces command authority, single incident commander invariant, transactional transfer,
and emergency succession protocols.
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
    IncidentCommandStructure,
    IncidentCommandAssignment,
    IncidentCommandHistory,
    utc_now,
)
from app.realtime.event_publisher import record_and_publish_event
from app.coordination.collaboration_service import log_inter_agency_audit

VALID_COMMAND_ROLES = {
    "INCIDENT_COMMANDER",
    "DEPUTY_COMMANDER",
    "SAFETY_OFFICER",
    "LIAISON_OFFICER",
    "PUBLIC_INFO_OFFICER",
    "OPERATIONS_CHIEF",
    "PLANNING_CHIEF",
    "LOGISTICS_CHIEF",
    "FINANCE_CHIEF",
    "EMS_BRANCH_DIRECTOR",
    "FIRE_BRANCH_DIRECTOR",
    "POLICE_BRANCH_DIRECTOR",
}


def get_active_command_structure(db: Session, incident_id: int) -> Optional[IncidentCommandStructure]:
    return (
        db.query(IncidentCommandStructure)
        .filter(
            IncidentCommandStructure.incident_id == incident_id,
            IncidentCommandStructure.is_active == True,
        )
        .first()
    )


def get_active_incident_commander(db: Session, command_structure_id: int) -> Optional[IncidentCommandAssignment]:
    return (
        db.query(IncidentCommandAssignment)
        .filter(
            IncidentCommandAssignment.command_structure_id == command_structure_id,
            IncidentCommandAssignment.command_role == "INCIDENT_COMMANDER",
            IncidentCommandAssignment.is_active == True,
        )
        .first()
    )


def establish_command_structure(
    db: Session,
    incident_id: int,
    structure_type: str,
    lead_agency_id: int,
    initial_commander_user_id: int,
    authorizing_user_id: int,
    activation_notes: Optional[str] = None,
    radio_callsign: Optional[str] = None,
    contact_number: Optional[str] = None,
) -> IncidentCommandStructure:
    """
    Establish an Incident Command Structure and assign the initial Incident Commander.
    Guarantees exactly one active commander at inception.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found.")

    lead_org = db.query(Organization).filter(Organization.id == lead_agency_id).first()
    if not lead_org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead organization {lead_agency_id} not found.")

    cmd_user = db.query(User).filter(User.id == initial_commander_user_id).first()
    if not cmd_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {initial_commander_user_id} not found.")

    # Check for existing active command structure
    existing_structure = get_active_command_structure(db, incident_id)
    if existing_structure:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active command structure already exists for incident {incident_id}."
        )

    struct_type = structure_type.upper()
    if struct_type not in ("SINGLE_COMMAND", "UNIFIED_COMMAND"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid structure type: {structure_type}")

    structure = IncidentCommandStructure(
        command_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        structure_type=struct_type,
        lead_agency_id=lead_agency_id,
        is_active=True,
        activation_notes=activation_notes,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(structure)
    db.flush()

    # Assign Initial Incident Commander
    commander_assignment = IncidentCommandAssignment(
        assignment_uuid=str(uuid.uuid4()),
        command_structure_id=structure.id,
        command_role="INCIDENT_COMMANDER",
        assigned_user_id=initial_commander_user_id,
        assigned_organization_id=lead_agency_id,
        is_active=True,
        radio_callsign=radio_callsign,
        contact_number=contact_number,
        assigned_at=utc_now(),
    )
    db.add(commander_assignment)

    # Record History
    history = IncidentCommandHistory(
        history_uuid=str(uuid.uuid4()),
        command_structure_id=structure.id,
        event_type="ESTABLISHED",
        previous_commander_id=None,
        new_commander_id=initial_commander_user_id,
        authorizing_user_id=authorizing_user_id,
        briefing_summary=activation_notes or "Initial command structure established",
        reason="Incident Command System initialized",
        created_at=utc_now(),
    )
    db.add(history)

    # Log Inter-Agency Audit
    log_inter_agency_audit(
        db=db,
        incident_id=incident_id,
        acting_org_id=lead_agency_id,
        acting_user_id=authorizing_user_id,
        action_type="COMMAND_ESTABLISHED",
        target_resource_type="INCIDENT_COMMAND_STRUCTURE",
        target_resource_id=structure.command_uuid,
        details={
            "structure_type": struct_type,
            "lead_agency_id": lead_agency_id,
            "commander_user_id": initial_commander_user_id,
        },
    )

    record_and_publish_event(
        db=db,
        event_type="command.structure.established",
        payload={
            "command_uuid": structure.command_uuid,
            "incident_id": incident_id,
            "structure_type": struct_type,
            "lead_agency_id": lead_agency_id,
            "commander_id": initial_commander_user_id,
        },
        organization_id=lead_agency_id,
        incident_id=incident_id,
        actor_id=authorizing_user_id,
    )

    db.commit()
    db.refresh(structure)
    return structure


def transfer_incident_commander(
    db: Session,
    command_structure_id: int,
    new_commander_user_id: int,
    new_commander_org_id: int,
    authorizing_user_id: int,
    briefing_summary: str,
    radio_callsign: Optional[str] = None,
    contact_number: Optional[str] = None,
) -> IncidentCommandAssignment:
    """
    Perform an atomic transfer of command.
    Relieves current commander and activates new commander within a single transaction.
    """
    structure = db.query(IncidentCommandStructure).filter(IncidentCommandStructure.id == command_structure_id).first()
    if not structure or not structure.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active command structure not found.")

    new_user = db.query(User).filter(User.id == new_commander_user_id).first()
    if not new_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {new_commander_user_id} not found.")

    new_org = db.query(Organization).filter(Organization.id == new_commander_org_id).first()
    if not new_org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization {new_commander_org_id} not found.")

    current_commander = get_active_incident_commander(db, command_structure_id)
    if not current_commander:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No active commander to relieve.")

    if current_commander.assigned_user_id == new_commander_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New commander is already the active incident commander.")

    # 1. Relieve current commander
    current_commander.is_active = False
    current_commander.relieved_at = utc_now()
    current_commander.relieved_by_user_id = authorizing_user_id

    # 2. Assign new commander
    new_assignment = IncidentCommandAssignment(
        assignment_uuid=str(uuid.uuid4()),
        command_structure_id=structure.id,
        command_role="INCIDENT_COMMANDER",
        assigned_user_id=new_commander_user_id,
        assigned_organization_id=new_commander_org_id,
        is_active=True,
        radio_callsign=radio_callsign,
        contact_number=contact_number,
        assigned_at=utc_now(),
    )
    db.add(new_assignment)

    # 3. Update structure lead agency if unified command transfer
    if structure.lead_agency_id != new_commander_org_id:
        structure.lead_agency_id = new_commander_org_id
        structure.updated_at = utc_now()

    # 4. Immutable Command History
    history = IncidentCommandHistory(
        history_uuid=str(uuid.uuid4()),
        command_structure_id=structure.id,
        event_type="COMMANDER_TRANSFERRED",
        previous_commander_id=current_commander.assigned_user_id,
        new_commander_id=new_commander_user_id,
        authorizing_user_id=authorizing_user_id,
        briefing_summary=briefing_summary,
        reason="Formal operational transfer of command",
        created_at=utc_now(),
    )
    db.add(history)

    # 5. Log inter-agency audit
    log_inter_agency_audit(
        db=db,
        incident_id=structure.incident_id,
        acting_org_id=new_commander_org_id,
        acting_user_id=authorizing_user_id,
        action_type="COMMANDER_TRANSFERRED",
        target_resource_type="INCIDENT_COMMANDER",
        target_resource_id=new_assignment.assignment_uuid,
        details={
            "previous_commander_id": current_commander.assigned_user_id,
            "new_commander_id": new_commander_user_id,
            "briefing_summary": briefing_summary,
        },
    )

    record_and_publish_event(
        db=db,
        event_type="command.commander.transferred",
        payload={
            "command_uuid": structure.command_uuid,
            "incident_id": structure.incident_id,
            "previous_commander_id": current_commander.assigned_user_id,
            "new_commander_id": new_commander_user_id,
            "new_commander_org_id": new_commander_org_id,
            "briefing_summary": briefing_summary,
        },
        organization_id=new_commander_org_id,
        incident_id=structure.incident_id,
        actor_id=authorizing_user_id,
    )

    db.commit()
    db.refresh(new_assignment)
    return new_assignment


def trigger_emergency_succession(
    db: Session,
    command_structure_id: int,
    successor_user_id: int,
    successor_org_id: int,
    authorizing_user_id: int,
    reason: str,
    briefing_summary: Optional[str] = None,
) -> IncidentCommandAssignment:
    """
    Emergency succession protocol when the current incident commander becomes unreachable or incapacitated.
    """
    structure = db.query(IncidentCommandStructure).filter(IncidentCommandStructure.id == command_structure_id).first()
    if not structure or not structure.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active command structure not found.")

    current_commander = get_active_incident_commander(db, command_structure_id)
    prev_commander_id = current_commander.assigned_user_id if current_commander else None

    if current_commander:
        current_commander.is_active = False
        current_commander.relieved_at = utc_now()
        current_commander.relieved_by_user_id = authorizing_user_id

    # Create successor assignment
    successor_assignment = IncidentCommandAssignment(
        assignment_uuid=str(uuid.uuid4()),
        command_structure_id=structure.id,
        command_role="INCIDENT_COMMANDER",
        assigned_user_id=successor_user_id,
        assigned_organization_id=successor_org_id,
        is_active=True,
        assigned_at=utc_now(),
    )
    db.add(successor_assignment)

    # Record History
    history = IncidentCommandHistory(
        history_uuid=str(uuid.uuid4()),
        command_structure_id=structure.id,
        event_type="EMERGENCY_SUCCESSION",
        previous_commander_id=prev_commander_id,
        new_commander_id=successor_user_id,
        authorizing_user_id=authorizing_user_id,
        briefing_summary=briefing_summary or "Emergency command succession triggered",
        reason=reason,
        created_at=utc_now(),
    )
    db.add(history)

    log_inter_agency_audit(
        db=db,
        incident_id=structure.incident_id,
        acting_org_id=successor_org_id,
        acting_user_id=authorizing_user_id,
        action_type="EMERGENCY_SUCCESSION_TRIGGERED",
        target_resource_type="INCIDENT_COMMANDER",
        target_resource_id=successor_assignment.assignment_uuid,
        details={
            "previous_commander_id": prev_commander_id,
            "successor_user_id": successor_user_id,
            "reason": reason,
        },
    )

    record_and_publish_event(
        db=db,
        event_type="command.succession.triggered",
        payload={
            "command_uuid": structure.command_uuid,
            "incident_id": structure.incident_id,
            "previous_commander_id": prev_commander_id,
            "successor_user_id": successor_user_id,
            "reason": reason,
        },
        organization_id=successor_org_id,
        incident_id=structure.incident_id,
        actor_id=authorizing_user_id,
    )

    db.commit()
    db.refresh(successor_assignment)
    return successor_assignment


def assign_subordinate_command_role(
    db: Session,
    command_structure_id: int,
    command_role: str,
    assigned_user_id: int,
    assigned_org_id: int,
    authorizing_user_id: int,
    radio_callsign: Optional[str] = None,
    contact_number: Optional[str] = None,
) -> IncidentCommandAssignment:
    structure = db.query(IncidentCommandStructure).filter(IncidentCommandStructure.id == command_structure_id).first()
    if not structure or not structure.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active command structure not found.")

    role_upper = command_role.upper()
    if role_upper not in VALID_COMMAND_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid command role: {command_role}")

    if role_upper == "INCIDENT_COMMANDER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign INCIDENT_COMMANDER via role assignment. Use transfer_incident_commander."
        )

    # Deactivate existing holder of this role if any
    existing_role = (
        db.query(IncidentCommandAssignment)
        .filter(
            IncidentCommandAssignment.command_structure_id == command_structure_id,
            IncidentCommandAssignment.command_role == role_upper,
            IncidentCommandAssignment.is_active == True,
        )
        .first()
    )
    if existing_role:
        existing_role.is_active = False
        existing_role.relieved_at = utc_now()
        existing_role.relieved_by_user_id = authorizing_user_id

    assignment = IncidentCommandAssignment(
        assignment_uuid=str(uuid.uuid4()),
        command_structure_id=command_structure_id,
        command_role=role_upper,
        assigned_user_id=assigned_user_id,
        assigned_organization_id=assigned_org_id,
        is_active=True,
        radio_callsign=radio_callsign,
        contact_number=contact_number,
        assigned_at=utc_now(),
    )
    db.add(assignment)

    history = IncidentCommandHistory(
        history_uuid=str(uuid.uuid4()),
        command_structure_id=command_structure_id,
        event_type="ROLE_ASSIGNED",
        previous_commander_id=None,
        new_commander_id=assigned_user_id,
        authorizing_user_id=authorizing_user_id,
        briefing_summary=f"Assigned to {role_upper}",
        reason=f"Role assignment: {role_upper}",
        created_at=utc_now(),
    )
    db.add(history)

    db.commit()
    db.refresh(assignment)
    return assignment
