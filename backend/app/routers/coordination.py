"""
CareOn Milestone 11 — Multi-Agency Coordination & Unified Incident Command Router.

Namespace: /api/coordination/v1
Endpoints for:
- Agency Classification & mutual aid directory
- Incident Collaboration & scope-based information governance
- Incident Command System (ICS) single commander enforcement, transfer, and emergency succession
- Cross-agency operational task lifecycle
- Inter-agency mutual aid resource requests (non-automatic dispatch)
- Geospatial operational zones (perimeters, hot/warm/cold, hazards)
- Scoped Common Operational Picture (COP)
- Inter-agency immutable audit logs
- Background maintenance sweeper
"""

import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User,
    Incident,
    Organization,
    OrganizationMembership,
    AgencyClassification,
    IncidentAgencyCollaboration,
    IncidentInformationGrant,
    IncidentCommandStructure,
    IncidentCommandAssignment,
    IncidentCommandHistory,
    AgencyOperationalTask,
    AgencyResourceRequest,
    IncidentOperationalZone,
    InterAgencyAuditLog,
)
from app.rbac.dependencies import get_current_user_flexible
from app.schemas import (
    AgencyClassificationCreate,
    AgencyClassificationUpdate,
    AgencyClassificationResponse,
    IncidentCollaborationInviteRequest,
    IncidentCollaborationActionRequest,
    IncidentCollaborationResponse,
    InformationGrantRequest,
    InformationGrantResponse,
    IncidentCommandCreateRequest,
    IncidentCommandTransferRequest,
    IncidentCommandSuccessionRequest,
    IncidentCommandAssignRoleRequest,
    IncidentCommandAssignmentResponse,
    IncidentCommandHistoryResponse,
    IncidentCommandStructureResponse,
    AgencyTaskCreateRequest,
    AgencyTaskUpdateRequest,
    AgencyTaskResponse,
    AgencyResourceRequestCreate,
    AgencyResourceRequestAction,
    AgencyResourceRequestResponse,
    IncidentOperationalZoneCreate,
    IncidentOperationalZoneResponse,
    OperationalPictureResponse,
    InterAgencyAuditResponse,
)
import app.coordination as coord_svc

router = APIRouter(prefix="/api/coordination/v1", tags=["Multi-Agency Coordination & Unified Command"])


def _extract_user_org_id(user: User, db: Session) -> Optional[int]:
    """Helper to extract user's primary organization ID."""
    if getattr(user, "organization_id", None):
        return user.organization_id
    if user.organization_memberships:
        return user.organization_memberships[0].organization_id
    membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active")
        .first()
    )
    return membership.organization_id if membership else None


def _user_name(u: Optional[User]) -> Optional[str]:
    if not u:
        return None
    return getattr(u, "name", None) or getattr(u, "full_name", None) or getattr(u, "email", None)


# ==============================================================================
# 1. Agency Classification & Mutual Aid Registry
# ==============================================================================

@router.post("/agencies/{organization_id}/classification", response_model=AgencyClassificationResponse)
def set_agency_classification(
    organization_id: int,
    data: AgencyClassificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    classification = coord_svc.register_or_update_classification(
        db=db,
        organization_id=organization_id,
        data=data,
    )
    return classification


@router.get("/agencies/{organization_id}/classification", response_model=AgencyClassificationResponse)
def get_agency_classification(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    classification = coord_svc.get_agency_classification(db, organization_id)
    if not classification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classification not found for organization {organization_id}."
        )
    return classification


@router.get("/mutual-aid-partners", response_model=List[Dict[str, Any]])
def list_mutual_aid_partners(
    agency_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    user_org_id = _extract_user_org_id(current_user, db) or 0
    partners = coord_svc.get_mutual_aid_partners(db, current_org_id=user_org_id, agency_type=agency_type)
    return partners


# ==============================================================================
# 2. Incident Collaborations & Scope Grants
# ==============================================================================

@router.post("/incidents/{incident_id}/collaborations/invite", response_model=IncidentCollaborationResponse)
def invite_agency(
    incident_id: int,
    req: IncidentCollaborationInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    inviting_org_id = _extract_user_org_id(current_user, db)
    if not inviting_org_id and current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must belong to an organization.")

    collab = coord_svc.invite_agency_to_incident(
        db=db,
        incident_id=incident_id,
        inviting_org_id=inviting_org_id or 1,
        inviting_user_id=current_user.id,
        target_org_id=req.target_organization_id,
        purpose=req.collaboration_purpose,
        initial_scopes=req.initial_scopes,
        expires_hours=req.expires_hours,
    )

    # Active scopes
    active_scopes = [g.scope for g in collab.information_grants if g.is_granted]
    return IncidentCollaborationResponse(
        id=collab.id,
        collaboration_uuid=collab.collaboration_uuid,
        incident_id=collab.incident_id,
        organization_id=collab.organization_id,
        organization_name=collab.organization.name if collab.organization else None,
        organization_type=collab.organization.org_type if collab.organization else None,
        collaboration_status=collab.collaboration_status,
        collaboration_purpose=collab.collaboration_purpose,
        inviting_organization_id=collab.inviting_organization_id,
        inviting_organization_name=collab.inviting_organization.name if collab.inviting_organization else None,
        accepted_at=collab.accepted_at,
        expires_at=collab.expires_at,
        revoked_at=collab.revoked_at,
        revoked_reason=collab.revoked_reason,
        active_scopes=active_scopes,
        created_at=collab.created_at,
        updated_at=collab.updated_at,
    )


@router.post("/collaborations/{collaboration_id}/action", response_model=IncidentCollaborationResponse)
def respond_collaboration(
    collaboration_id: int,
    req: IncidentCollaborationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    acting_org_id = _extract_user_org_id(current_user, db) or 1
    collab = coord_svc.respond_to_collaboration(
        db=db,
        collaboration_id=collaboration_id,
        acting_org_id=acting_org_id,
        acting_user_id=current_user.id,
        new_status=req.status,
        reason=req.reason,
    )
    active_scopes = [g.scope for g in collab.information_grants if g.is_granted]
    return IncidentCollaborationResponse(
        id=collab.id,
        collaboration_uuid=collab.collaboration_uuid,
        incident_id=collab.incident_id,
        organization_id=collab.organization_id,
        organization_name=collab.organization.name if collab.organization else None,
        organization_type=collab.organization.org_type if collab.organization else None,
        collaboration_status=collab.collaboration_status,
        collaboration_purpose=collab.collaboration_purpose,
        inviting_organization_id=collab.inviting_organization_id,
        inviting_organization_name=collab.inviting_organization.name if collab.inviting_organization else None,
        accepted_at=collab.accepted_at,
        expires_at=collab.expires_at,
        revoked_at=collab.revoked_at,
        revoked_reason=collab.revoked_reason,
        active_scopes=active_scopes,
        created_at=collab.created_at,
        updated_at=collab.updated_at,
    )


@router.put("/collaborations/{collaboration_id}/grants", response_model=List[InformationGrantResponse])
def update_grants(
    collaboration_id: int,
    req: InformationGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    acting_org_id = _extract_user_org_id(current_user, db) or 1
    grants = coord_svc.update_information_grants(
        db=db,
        collaboration_id=collaboration_id,
        acting_org_id=acting_org_id,
        acting_user_id=current_user.id,
        scopes_to_grant=req.scopes_to_grant,
        scopes_to_revoke=req.scopes_to_revoke,
    )
    return [
        InformationGrantResponse(
            grant_uuid=g.grant_uuid,
            collaboration_id=g.collaboration_id,
            scope=g.scope,
            is_granted=g.is_granted,
            granted_at=g.granted_at,
            revoked_at=g.revoked_at,
        )
        for g in grants
    ]


@router.get("/incidents/{incident_id}/collaborations", response_model=List[IncidentCollaborationResponse])
def list_incident_collaborations(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    collabs = (
        db.query(IncidentAgencyCollaboration)
        .filter(IncidentAgencyCollaboration.incident_id == incident_id)
        .all()
    )
    results = []
    for c in collabs:
        active_scopes = [g.scope for g in c.information_grants if g.is_granted]
        results.append(
            IncidentCollaborationResponse(
                id=c.id,
                collaboration_uuid=c.collaboration_uuid,
                incident_id=c.incident_id,
                organization_id=c.organization_id,
                organization_name=c.organization.name if c.organization else None,
                organization_type=c.organization.org_type if c.organization else None,
                collaboration_status=c.collaboration_status,
                collaboration_purpose=c.collaboration_purpose,
                inviting_organization_id=c.inviting_organization_id,
                inviting_organization_name=c.inviting_organization.name if c.inviting_organization else None,
                accepted_at=c.accepted_at,
                expires_at=c.expires_at,
                revoked_at=c.revoked_at,
                revoked_reason=c.revoked_reason,
                active_scopes=active_scopes,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return results


# ==============================================================================
# 3. Incident Command (ICS)
# ==============================================================================

@router.post("/incidents/{incident_id}/command/establish", response_model=IncidentCommandStructureResponse)
def establish_command(
    incident_id: int,
    req: IncidentCommandCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    structure = coord_svc.establish_command_structure(
        db=db,
        incident_id=incident_id,
        structure_type=req.structure_type,
        lead_agency_id=req.lead_agency_id,
        initial_commander_user_id=req.initial_commander_user_id,
        authorizing_user_id=current_user.id,
        activation_notes=req.activation_notes,
        radio_callsign=req.radio_callsign,
        contact_number=req.contact_number,
    )
    active_cmd = coord_svc.get_active_incident_commander(db, structure.id)
    cmd_resp = None
    if active_cmd:
        cmd_resp = IncidentCommandAssignmentResponse(
            assignment_uuid=active_cmd.assignment_uuid,
            command_structure_id=active_cmd.command_structure_id,
            command_role=active_cmd.command_role,
            assigned_user_id=active_cmd.assigned_user_id,
            assigned_user_name=_user_name(active_cmd.assigned_user),
            assigned_organization_id=active_cmd.assigned_organization_id,
            assigned_organization_name=active_cmd.assigned_organization.name if active_cmd.assigned_organization else None,
            is_active=active_cmd.is_active,
            radio_callsign=active_cmd.radio_callsign,
            contact_number=active_cmd.contact_number,
            assigned_at=active_cmd.assigned_at,
            relieved_at=active_cmd.relieved_at,
        )

    return IncidentCommandStructureResponse(
        command_uuid=structure.command_uuid,
        incident_id=structure.incident_id,
        structure_type=structure.structure_type,
        lead_agency_id=structure.lead_agency_id,
        lead_agency_name=structure.lead_agency.name if structure.lead_agency else None,
        is_active=structure.is_active,
        activation_notes=structure.activation_notes,
        active_commander=cmd_resp,
        assignments=[cmd_resp] if cmd_resp else [],
        created_at=structure.created_at,
        updated_at=structure.updated_at,
    )


@router.post("/command/{command_structure_id}/transfer", response_model=IncidentCommandAssignmentResponse)
def transfer_commander(
    command_structure_id: int,
    req: IncidentCommandTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    assignment = coord_svc.transfer_incident_commander(
        db=db,
        command_structure_id=command_structure_id,
        new_commander_user_id=req.new_commander_user_id,
        new_commander_org_id=req.new_commander_org_id,
        authorizing_user_id=current_user.id,
        briefing_summary=req.briefing_summary,
        radio_callsign=req.radio_callsign,
        contact_number=req.contact_number,
    )
    return IncidentCommandAssignmentResponse(
        assignment_uuid=assignment.assignment_uuid,
        command_structure_id=assignment.command_structure_id,
        command_role=assignment.command_role,
        assigned_user_id=assignment.assigned_user_id,
        assigned_user_name=_user_name(assignment.assigned_user),
        assigned_organization_id=assignment.assigned_organization_id,
        assigned_organization_name=assignment.assigned_organization.name if assignment.assigned_organization else None,
        is_active=assignment.is_active,
        radio_callsign=assignment.radio_callsign,
        contact_number=assignment.contact_number,
        assigned_at=assignment.assigned_at,
        relieved_at=assignment.relieved_at,
    )


@router.post("/command/{command_structure_id}/succession", response_model=IncidentCommandAssignmentResponse)
def emergency_succession(
    command_structure_id: int,
    req: IncidentCommandSuccessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    assignment = coord_svc.trigger_emergency_succession(
        db=db,
        command_structure_id=command_structure_id,
        successor_user_id=req.new_commander_user_id,
        successor_org_id=req.new_commander_org_id,
        authorizing_user_id=current_user.id,
        reason=req.reason,
        briefing_summary=req.briefing_summary,
    )
    return IncidentCommandAssignmentResponse(
        assignment_uuid=assignment.assignment_uuid,
        command_structure_id=assignment.command_structure_id,
        command_role=assignment.command_role,
        assigned_user_id=assignment.assigned_user_id,
        assigned_user_name=_user_name(assignment.assigned_user),
        assigned_organization_id=assignment.assigned_organization_id,
        assigned_organization_name=assignment.assigned_organization.name if assignment.assigned_organization else None,
        is_active=assignment.is_active,
        radio_callsign=assignment.radio_callsign,
        contact_number=assignment.contact_number,
        assigned_at=assignment.assigned_at,
        relieved_at=assignment.relieved_at,
    )


@router.post("/command/{command_structure_id}/assign-role", response_model=IncidentCommandAssignmentResponse)
def assign_role(
    command_structure_id: int,
    req: IncidentCommandAssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    assignment = coord_svc.assign_subordinate_command_role(
        db=db,
        command_structure_id=command_structure_id,
        command_role=req.command_role,
        assigned_user_id=req.assigned_user_id,
        assigned_org_id=req.assigned_org_id,
        authorizing_user_id=current_user.id,
        radio_callsign=req.radio_callsign,
        contact_number=req.contact_number,
    )
    return IncidentCommandAssignmentResponse(
        assignment_uuid=assignment.assignment_uuid,
        command_structure_id=assignment.command_structure_id,
        command_role=assignment.command_role,
        assigned_user_id=assignment.assigned_user_id,
        assigned_user_name=_user_name(assignment.assigned_user),
        assigned_organization_id=assignment.assigned_organization_id,
        assigned_organization_name=assignment.assigned_organization.name if assignment.assigned_organization else None,
        is_active=assignment.is_active,
        radio_callsign=assignment.radio_callsign,
        contact_number=assignment.contact_number,
        assigned_at=assignment.assigned_at,
        relieved_at=assignment.relieved_at,
    )


@router.get("/incidents/{incident_id}/command", response_model=IncidentCommandStructureResponse)
def get_incident_command(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    structure = coord_svc.get_active_command_structure(db, incident_id)
    if not structure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active command structure found for incident {incident_id}."
        )

    assignments_resp = []
    active_cmd_resp = None
    for a in structure.assignments:
        resp = IncidentCommandAssignmentResponse(
            assignment_uuid=a.assignment_uuid,
            command_structure_id=a.command_structure_id,
            command_role=a.command_role,
            assigned_user_id=a.assigned_user_id,
            assigned_user_name=_user_name(a.assigned_user),
            assigned_organization_id=a.assigned_organization_id,
            assigned_organization_name=a.assigned_organization.name if a.assigned_organization else None,
            is_active=a.is_active,
            radio_callsign=a.radio_callsign,
            contact_number=a.contact_number,
            assigned_at=a.assigned_at,
            relieved_at=a.relieved_at,
        )
        assignments_resp.append(resp)
        if a.command_role == "INCIDENT_COMMANDER" and a.is_active:
            active_cmd_resp = resp

    return IncidentCommandStructureResponse(
        command_uuid=structure.command_uuid,
        incident_id=structure.incident_id,
        structure_type=structure.structure_type,
        lead_agency_id=structure.lead_agency_id,
        lead_agency_name=structure.lead_agency.name if structure.lead_agency else None,
        is_active=structure.is_active,
        activation_notes=structure.activation_notes,
        active_commander=active_cmd_resp,
        assignments=assignments_resp,
        created_at=structure.created_at,
        updated_at=structure.updated_at,
    )


@router.get("/command/{command_structure_id}/history", response_model=List[IncidentCommandHistoryResponse])
def get_command_history(
    command_structure_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    histories = (
        db.query(IncidentCommandHistory)
        .filter(IncidentCommandHistory.command_structure_id == command_structure_id)
        .order_by(IncidentCommandHistory.created_at.asc())
        .all()
    )
    return [
        IncidentCommandHistoryResponse(
            history_uuid=h.history_uuid,
            event_type=h.event_type,
            previous_commander_id=h.previous_commander_id,
            new_commander_id=h.new_commander_id,
            authorizing_user_id=h.authorizing_user_id,
            briefing_summary=h.briefing_summary,
            reason=h.reason,
            created_at=h.created_at,
        )
        for h in histories
    ]


# ==============================================================================
# 4. Operational Tasks
# ==============================================================================

@router.post("/incidents/{incident_id}/tasks", response_model=AgencyTaskResponse)
def create_task(
    incident_id: int,
    req: AgencyTaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    assigning_org_id = _extract_user_org_id(current_user, db) or 1
    task = coord_svc.create_operational_task(
        db=db,
        incident_id=incident_id,
        assigning_org_id=assigning_org_id,
        assigned_org_id=req.assigned_organization_id,
        created_by_user_id=current_user.id,
        title=req.title,
        description=req.description,
        priority=req.priority,
        assigned_unit_name=req.assigned_unit_name,
        deadline=req.deadline,
    )
    return AgencyTaskResponse(
        id=task.id,
        task_uuid=task.task_uuid,
        incident_id=task.incident_id,
        command_structure_id=task.command_structure_id,
        assigning_organization_id=task.assigning_organization_id,
        assigning_organization_name=task.assigning_organization.name if task.assigning_organization else None,
        assigned_organization_id=task.assigned_organization_id,
        assigned_organization_name=task.assigned_organization.name if task.assigned_organization else None,
        created_by_user_id=task.created_by_user_id,
        created_by_name=_user_name(task.created_by),
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        assigned_unit_name=task.assigned_unit_name,
        deadline=task.deadline,
        acknowledged_at=task.acknowledged_at,
        completed_at=task.completed_at,
        rejection_reason=task.rejection_reason,
        status_notes=task.status_notes,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.put("/tasks/{task_id}", response_model=AgencyTaskResponse)
def update_task(
    task_id: int,
    req: AgencyTaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    acting_org_id = _extract_user_org_id(current_user, db) or 1
    task = coord_svc.update_operational_task_status(
        db=db,
        task_id=task_id,
        acting_org_id=acting_org_id,
        acting_user_id=current_user.id,
        new_status=req.status,
        assigned_unit_name=req.assigned_unit_name,
        rejection_reason=req.rejection_reason,
        status_notes=req.status_notes,
    )
    return AgencyTaskResponse(
        id=task.id,
        task_uuid=task.task_uuid,
        incident_id=task.incident_id,
        command_structure_id=task.command_structure_id,
        assigning_organization_id=task.assigning_organization_id,
        assigning_organization_name=task.assigning_organization.name if task.assigning_organization else None,
        assigned_organization_id=task.assigned_organization_id,
        assigned_organization_name=task.assigned_organization.name if task.assigned_organization else None,
        created_by_user_id=task.created_by_user_id,
        created_by_name=_user_name(task.created_by),
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        assigned_unit_name=task.assigned_unit_name,
        deadline=task.deadline,
        acknowledged_at=task.acknowledged_at,
        completed_at=task.completed_at,
        rejection_reason=task.rejection_reason,
        status_notes=task.status_notes,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/incidents/{incident_id}/tasks", response_model=List[AgencyTaskResponse])
def list_incident_tasks(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    tasks = (
        db.query(AgencyOperationalTask)
        .filter(AgencyOperationalTask.incident_id == incident_id)
        .order_by(AgencyOperationalTask.created_at.desc())
        .all()
    )
    return [
        AgencyTaskResponse(
            id=t.id,
            task_uuid=t.task_uuid,
            incident_id=t.incident_id,
            command_structure_id=t.command_structure_id,
            assigning_organization_id=t.assigning_organization_id,
            assigning_organization_name=t.assigning_organization.name if t.assigning_organization else None,
            assigned_organization_id=t.assigned_organization_id,
            assigned_organization_name=t.assigned_organization.name if t.assigned_organization else None,
            created_by_user_id=t.created_by_user_id,
            created_by_name=_user_name(t.created_by),
            title=t.title,
            description=t.description,
            priority=t.priority,
            status=t.status,
            assigned_unit_name=t.assigned_unit_name,
            deadline=t.deadline,
            acknowledged_at=t.acknowledged_at,
            completed_at=t.completed_at,
            rejection_reason=t.rejection_reason,
            status_notes=t.status_notes,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tasks
    ]


# ==============================================================================
# 5. Mutual Aid Resource Requests
# ==============================================================================

@router.post("/incidents/{incident_id}/resource-requests", response_model=AgencyResourceRequestResponse)
def create_mutual_aid_request(
    incident_id: int,
    req: AgencyResourceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    requesting_org_id = _extract_user_org_id(current_user, db) or 1
    res_req = coord_svc.create_resource_request(
        db=db,
        incident_id=incident_id,
        requesting_org_id=requesting_org_id,
        requested_org_id=req.requested_organization_id,
        requested_by_user_id=current_user.id,
        resource_type=req.resource_type,
        quantity=req.quantity,
        urgency=req.urgency,
        operational_justification=req.operational_justification,
        staging_location_name=req.staging_location_name,
        staging_latitude=req.staging_latitude,
        staging_longitude=req.staging_longitude,
        expires_hours=req.expires_hours,
    )
    assigned_resources = json.loads(res_req.assigned_resource_ids_json) if res_req.assigned_resource_ids_json else []
    return AgencyResourceRequestResponse(
        id=res_req.id,
        request_uuid=res_req.request_uuid,
        incident_id=res_req.incident_id,
        requesting_organization_id=res_req.requesting_organization_id,
        requesting_organization_name=res_req.requesting_organization.name if res_req.requesting_organization else None,
        requested_organization_id=res_req.requested_organization_id,
        requested_organization_name=res_req.requested_organization.name if res_req.requested_organization else None,
        resource_type=res_req.resource_type,
        quantity=res_req.quantity,
        urgency=res_req.urgency,
        status=res_req.status,
        operational_justification=res_req.operational_justification,
        staging_location_name=res_req.staging_location_name,
        staging_latitude=res_req.staging_latitude,
        staging_longitude=res_req.staging_longitude,
        decision_notes=res_req.decision_notes,
        assigned_resource_ids=assigned_resources,
        expires_at=res_req.expires_at,
        created_at=res_req.created_at,
        updated_at=res_req.updated_at,
    )


@router.post("/resource-requests/{request_id}/action", response_model=AgencyResourceRequestResponse)
def action_mutual_aid_request(
    request_id: int,
    req: AgencyResourceRequestAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    acting_org_id = _extract_user_org_id(current_user, db) or 1
    res_req = coord_svc.action_resource_request(
        db=db,
        request_id=request_id,
        acting_org_id=acting_org_id,
        acting_user_id=current_user.id,
        action=req.action,
        decision_notes=req.decision_notes,
        assigned_resource_ids=req.assigned_resource_ids,
    )
    assigned_resources = json.loads(res_req.assigned_resource_ids_json) if res_req.assigned_resource_ids_json else []
    return AgencyResourceRequestResponse(
        id=res_req.id,
        request_uuid=res_req.request_uuid,
        incident_id=res_req.incident_id,
        requesting_organization_id=res_req.requesting_organization_id,
        requesting_organization_name=res_req.requesting_organization.name if res_req.requesting_organization else None,
        requested_organization_id=res_req.requested_organization_id,
        requested_organization_name=res_req.requested_organization.name if res_req.requested_organization else None,
        resource_type=res_req.resource_type,
        quantity=res_req.quantity,
        urgency=res_req.urgency,
        status=res_req.status,
        operational_justification=res_req.operational_justification,
        staging_location_name=res_req.staging_location_name,
        staging_latitude=res_req.staging_latitude,
        staging_longitude=res_req.staging_longitude,
        decision_notes=res_req.decision_notes,
        assigned_resource_ids=assigned_resources,
        expires_at=res_req.expires_at,
        created_at=res_req.created_at,
        updated_at=res_req.updated_at,
    )


@router.get("/incidents/{incident_id}/resource-requests", response_model=List[AgencyResourceRequestResponse])
def list_incident_resource_requests(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    reqs = (
        db.query(AgencyResourceRequest)
        .filter(AgencyResourceRequest.incident_id == incident_id)
        .order_by(AgencyResourceRequest.created_at.desc())
        .all()
    )
    results = []
    for r in reqs:
        assigned_resources = json.loads(r.assigned_resource_ids_json) if r.assigned_resource_ids_json else []
        results.append(
            AgencyResourceRequestResponse(
                id=r.id,
                request_uuid=r.request_uuid,
                incident_id=r.incident_id,
                requesting_organization_id=r.requesting_organization_id,
                requesting_organization_name=r.requesting_organization.name if r.requesting_organization else None,
                requested_organization_id=r.requested_organization_id,
                requested_organization_name=r.requested_organization.name if r.requested_organization else None,
                resource_type=r.resource_type,
                quantity=r.quantity,
                urgency=r.urgency,
                status=r.status,
                operational_justification=r.operational_justification,
                staging_location_name=r.staging_location_name,
                staging_latitude=r.staging_latitude,
                staging_longitude=r.staging_longitude,
                decision_notes=r.decision_notes,
                assigned_resource_ids=assigned_resources,
                expires_at=r.expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return results


# ==============================================================================
# 6. Operational Zones & Common Operational Picture (COP)
# ==============================================================================

@router.post("/incidents/{incident_id}/zones", response_model=IncidentOperationalZoneResponse)
def create_zone(
    incident_id: int,
    req: IncidentOperationalZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    acting_org_id = _extract_user_org_id(current_user, db) or 1
    zone = coord_svc.create_operational_zone(
        db=db,
        incident_id=incident_id,
        acting_org_id=acting_org_id,
        acting_user_id=current_user.id,
        zone_type=req.zone_type,
        name=req.name,
        description=req.description,
        center_latitude=req.center_latitude,
        center_longitude=req.center_longitude,
        radius_meters=req.radius_meters,
        polygon_geojson=req.polygon_geojson,
        hazard_type=req.hazard_type,
        access_restrictions=req.access_restrictions,
    )
    return IncidentOperationalZoneResponse(
        zone_uuid=zone.zone_uuid,
        incident_id=zone.incident_id,
        created_by_organization_id=zone.created_by_organization_id,
        created_by_organization_name=zone.created_by_organization.name if zone.created_by_organization else None,
        zone_type=zone.zone_type,
        name=zone.name,
        description=zone.description,
        center_latitude=zone.center_latitude,
        center_longitude=zone.center_longitude,
        radius_meters=zone.radius_meters,
        polygon_geojson=zone.polygon_geojson,
        hazard_type=zone.hazard_type,
        access_restrictions=zone.access_restrictions,
        is_active=zone.is_active,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


@router.get("/incidents/{incident_id}/zones", response_model=List[IncidentOperationalZoneResponse])
def list_zones(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    zones = (
        db.query(IncidentOperationalZone)
        .filter(IncidentOperationalZone.incident_id == incident_id, IncidentOperationalZone.is_active == True)
        .all()
    )
    return [
        IncidentOperationalZoneResponse(
            zone_uuid=z.zone_uuid,
            incident_id=z.incident_id,
            created_by_organization_id=z.created_by_organization_id,
            created_by_organization_name=z.created_by_organization.name if z.created_by_organization else None,
            zone_type=z.zone_type,
            name=z.name,
            description=z.description,
            center_latitude=z.center_latitude,
            center_longitude=z.center_longitude,
            radius_meters=z.radius_meters,
            polygon_geojson=z.polygon_geojson,
            hazard_type=z.hazard_type,
            access_restrictions=z.access_restrictions,
            is_active=z.is_active,
            created_at=z.created_at,
            updated_at=z.updated_at,
        )
        for z in zones
    ]


@router.get("/incidents/{incident_id}/operational-picture", response_model=OperationalPictureResponse)
def get_operational_picture(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    cop = coord_svc.get_incident_operational_picture(
        db=db,
        incident_id=incident_id,
        requesting_org_id=_extract_user_org_id(current_user, db),
        requesting_user_id=current_user.id,
        is_superadmin=(current_user.role == "super_admin"),
    )
    return cop


# ==============================================================================
# 7. Inter-Agency Audit Logs
# ==============================================================================

@router.get("/incidents/{incident_id}/audit-logs", response_model=List[InterAgencyAuditResponse])
def get_inter_agency_audits(
    incident_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    logs = (
        db.query(InterAgencyAuditLog)
        .filter(InterAgencyAuditLog.incident_id == incident_id)
        .order_by(InterAgencyAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        InterAgencyAuditResponse(
            audit_uuid=l.audit_uuid,
            incident_id=l.incident_id,
            acting_organization_id=l.acting_organization_id,
            acting_organization_name=l.acting_organization.name if l.acting_organization else None,
            acting_user_id=l.acting_user_id,
            acting_user_name=_user_name(l.acting_user),
            action_type=l.action_type,
            target_agency_id=l.target_agency_id,
            target_agency_name=l.target_agency.name if l.target_agency else None,
            target_resource_type=l.target_resource_type,
            target_resource_id=l.target_resource_id,
            details=json.loads(l.details_json) if l.details_json else None,
            created_at=l.created_at,
        )
        for l in logs
    ]


# ==============================================================================
# 8. Background Maintenance Worker Sweep
# ==============================================================================

@router.post("/worker/sweep-expiries", response_model=Dict[str, int])
def run_worker_sweep(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    stats = coord_svc.sweep_coordination_expiries(db)
    return stats
