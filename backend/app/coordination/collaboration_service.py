"""
Cross-Agency Collaboration and Information Governance Service.
Enforces multi-tenant isolation, granular scope-based grants, and audit logging.
Deny-by-default: Knowing an incident ID gives zero access without explicit authorization.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    Incident,
    Organization,
    User,
    IncidentAgencyCollaboration,
    IncidentInformationGrant,
    InterAgencyAuditLog,
    utc_now,
)
from app.realtime.event_publisher import record_and_publish_event

VALID_SCOPES = {
    "INCIDENT_SUMMARY",
    "OPERATIONAL_LOCATION",
    "HAZARD_INFORMATION",
    "RESOURCE_STATUS",
    "AGENCY_TASKS",
    "CASUALTY_COUNTS",
    "HOSPITAL_DESTINATION",
    "CLINICAL_HANDOVER_REFERENCE",
    "COMMAND_INFORMATION",
    "OPERATIONAL_DOCUMENTS",
}


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def log_inter_agency_audit(
    db: Session,
    incident_id: int,
    acting_org_id: int,
    acting_user_id: int,
    action_type: str,
    target_agency_id: Optional[int] = None,
    target_resource_type: Optional[str] = None,
    target_resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> InterAgencyAuditLog:
    """
    Append an immutable cross-agency audit log record.
    """
    audit = InterAgencyAuditLog(
        audit_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        acting_organization_id=acting_org_id,
        acting_user_id=acting_user_id,
        action_type=action_type,
        target_agency_id=target_agency_id,
        target_resource_type=target_resource_type,
        target_resource_id=target_resource_id,
        details_json=json.dumps(details) if details else None,
        ip_address=ip_address,
        created_at=utc_now(),
    )
    db.add(audit)
    db.flush()
    return audit


def get_active_collaboration_scopes(
    db: Session,
    incident_id: int,
    org_id: int,
) -> Tuple[bool, Set[str], Optional[IncidentAgencyCollaboration]]:
    """
    Retrieve active collaboration and granted scopes for an organization on an incident.
    Returns: (is_active, granted_scopes_set, collaboration_record)
    """
    collab = (
        db.query(IncidentAgencyCollaboration)
        .filter(
            IncidentAgencyCollaboration.incident_id == incident_id,
            IncidentAgencyCollaboration.organization_id == org_id,
        )
        .first()
    )

    if not collab:
        return False, set(), None

    if collab.collaboration_status not in ("ACCEPTED", "ACTIVE"):
        return False, set(), collab

    # Check expiry
    if collab.expires_at and ensure_utc(collab.expires_at) < utc_now():
        return False, set(), collab

    # Collect granted scopes
    grants = (
        db.query(IncidentInformationGrant)
        .filter(
            IncidentInformationGrant.collaboration_id == collab.id,
            IncidentInformationGrant.is_granted == True,
            IncidentInformationGrant.revoked_at.is_(None),
        )
        .all()
    )
    scopes = {g.scope for g in grants}
    return True, scopes, collab


def verify_incident_scope_access(
    db: Session,
    incident_id: int,
    user_org_id: Optional[int],
    user_id: int,
    required_scope: Optional[str] = None,
    is_superadmin: bool = False,
) -> Set[str]:
    """
    Strict authorization gate:
    1. Superadmin has full access to all valid scopes.
    2. Primary lead agency (incident creator / assigned agency) has full scopes.
    3. Collaborating agencies only have explicitly granted scopes.
    4. Non-collaborating agencies are rejected with 403 Forbidden.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found."
        )

    if is_superadmin:
        return VALID_SCOPES.copy()

    if not user_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no associated organization."
        )

    # If the user belongs to the primary organization of the incident
    if incident.user_id:
        creator_membership = (
            db.query(Organization)
            .join(IncidentAgencyCollaboration, IncidentAgencyCollaboration.organization_id == Organization.id, isouter=True)
            .filter(Organization.id == user_org_id)
            .first()
        )
        from app.models import OrganizationMembership
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == incident.user_id,
            OrganizationMembership.organization_id == user_org_id,
            OrganizationMembership.status == "active",
        ).first()
        if membership:
            return VALID_SCOPES.copy()

    from app.models import IncidentCommandStructure
    cmd_struct = (
        db.query(IncidentCommandStructure)
        .filter(
            IncidentCommandStructure.incident_id == incident_id,
            IncidentCommandStructure.is_active == True,
        )
        .first()
    )
    if cmd_struct and cmd_struct.lead_agency_id == user_org_id:
        return VALID_SCOPES.copy()

    # Check inter-agency collaboration
    is_active, active_scopes, collab = get_active_collaboration_scopes(db, incident_id, user_org_id)
    if not is_active:
        log_inter_agency_audit(
            db=db,
            incident_id=incident_id,
            acting_org_id=user_org_id,
            acting_user_id=user_id,
            action_type="ACCESS_DENIED_NO_ACTIVE_COLLABORATION",
            details={"requested_scope": required_scope},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Organization {user_org_id} has no active collaboration with incident {incident_id}."
        )

    if required_scope and required_scope not in active_scopes:
        log_inter_agency_audit(
            db=db,
            incident_id=incident_id,
            acting_org_id=user_org_id,
            acting_user_id=user_id,
            action_type="ACCESS_DENIED_SCOPE_NOT_GRANTED",
            details={"required_scope": required_scope, "active_scopes": list(active_scopes)},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: organization lacks '{required_scope}' grant for incident {incident_id}."
        )

    return active_scopes


def invite_agency_to_incident(
    db: Session,
    incident_id: int,
    inviting_org_id: int,
    inviting_user_id: int,
    target_org_id: int,
    purpose: str,
    initial_scopes: List[str],
    expires_hours: Optional[int] = 24,
) -> IncidentAgencyCollaboration:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found.")

    target_org = db.query(Organization).filter(Organization.id == target_org_id).first()
    if not target_org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target organization {target_org_id} not found.")

    if inviting_org_id == target_org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot invite self organization to incident.")

    # Validate scopes
    invalid_scopes = set(initial_scopes) - VALID_SCOPES
    if invalid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes requested: {list(invalid_scopes)}"
        )

    # Check existing collaboration
    existing = (
        db.query(IncidentAgencyCollaboration)
        .filter(
            IncidentAgencyCollaboration.incident_id == incident_id,
            IncidentAgencyCollaboration.organization_id == target_org_id,
        )
        .first()
    )

    expires_at = utc_now() + timedelta(hours=expires_hours) if expires_hours else None

    if existing:
        if existing.collaboration_status in ("ACCEPTED", "ACTIVE"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization {target_org_id} is already collaborating on incident {incident_id}."
            )
        # Re-invite or renew
        existing.collaboration_status = "INVITED"
        existing.inviting_organization_id = inviting_org_id
        existing.inviting_user_id = inviting_user_id
        existing.collaboration_purpose = purpose
        existing.expires_at = expires_at
        existing.revoked_at = None
        existing.revoked_reason = None
        existing.updated_at = utc_now()
        collab = existing
    else:
        collab = IncidentAgencyCollaboration(
            collaboration_uuid=str(uuid.uuid4()),
            incident_id=incident_id,
            organization_id=target_org_id,
            collaboration_status="INVITED",
            inviting_organization_id=inviting_org_id,
            inviting_user_id=inviting_user_id,
            collaboration_purpose=purpose,
            expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(collab)
        db.flush()

    # Create/update initial scope grants
    for scope_name in initial_scopes:
        grant = (
            db.query(IncidentInformationGrant)
            .filter(
                IncidentInformationGrant.collaboration_id == collab.id,
                IncidentInformationGrant.scope == scope_name,
            )
            .first()
        )
        if not grant:
            grant = IncidentInformationGrant(
                grant_uuid=str(uuid.uuid4()),
                collaboration_id=collab.id,
                scope=scope_name,
                is_granted=True,
                granted_by_user_id=inviting_user_id,
                granted_at=utc_now(),
            )
            db.add(grant)
        else:
            grant.is_granted = True
            grant.revoked_at = None
            grant.granted_at = utc_now()

    # Log audit
    log_inter_agency_audit(
        db=db,
        incident_id=incident_id,
        acting_org_id=inviting_org_id,
        acting_user_id=inviting_user_id,
        action_type="COLLABORATION_INVITED",
        target_agency_id=target_org_id,
        details={"purpose": purpose, "initial_scopes": initial_scopes, "expires_at": expires_at.isoformat() if expires_at else None},
    )

    # Publish Realtime event
    record_and_publish_event(
        db=db,
        event_type="inter_agency.collaboration.invited",
        payload={
            "collaboration_uuid": collab.collaboration_uuid,
            "incident_id": incident_id,
            "target_organization_id": target_org_id,
            "inviting_organization_id": inviting_org_id,
            "purpose": purpose,
        },
        organization_id=target_org_id,
        incident_id=incident_id,
        actor_id=inviting_user_id,
    )

    db.commit()
    db.refresh(collab)
    return collab


def respond_to_collaboration(
    db: Session,
    collaboration_id: int,
    acting_org_id: int,
    acting_user_id: int,
    new_status: str,
    reason: Optional[str] = None,
) -> IncidentAgencyCollaboration:
    collab = db.query(IncidentAgencyCollaboration).filter(IncidentAgencyCollaboration.id == collaboration_id).first()
    if not collab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found.")

    new_status_upper = new_status.upper()
    if new_status_upper not in ("ACCEPTED", "SUSPENDED", "REVOKED", "COMPLETED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid collaboration status: {new_status}")

    # Check permissions: target org can ACCEPT or DECLINE/REVOKE; inviting org or lead can SUSPEND, REVOKE, COMPLETE
    is_target_org = (collab.organization_id == acting_org_id)
    is_inviting_org = (collab.inviting_organization_id == acting_org_id)

    if new_status_upper == "ACCEPTED":
        if not is_target_org:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only invited agency can accept collaboration.")
        collab.collaboration_status = "ACCEPTED"
        collab.accepted_by_user_id = acting_user_id
        collab.accepted_at = utc_now()
        event_type = "inter_agency.collaboration.accepted"
    elif new_status_upper == "REVOKED":
        collab.collaboration_status = "REVOKED"
        collab.revoked_by_user_id = acting_user_id
        collab.revoked_at = utc_now()
        collab.revoked_reason = reason or "Revoked by authorized agency"
        event_type = "inter_agency.collaboration.revoked"
    elif new_status_upper == "SUSPENDED":
        collab.collaboration_status = "SUSPENDED"
        collab.revoked_by_user_id = acting_user_id
        collab.revoked_at = utc_now()
        collab.revoked_reason = reason or "Suspended"
        event_type = "inter_agency.collaboration.suspended"
    else:  # COMPLETED
        collab.collaboration_status = "COMPLETED"
        event_type = "inter_agency.collaboration.completed"

    collab.updated_at = utc_now()

    # Log audit
    log_inter_agency_audit(
        db=db,
        incident_id=collab.incident_id,
        acting_org_id=acting_org_id,
        acting_user_id=acting_user_id,
        action_type=f"COLLABORATION_{new_status_upper}",
        target_agency_id=collab.organization_id if not is_target_org else collab.inviting_organization_id,
        details={"status": new_status_upper, "reason": reason},
    )

    record_and_publish_event(
        db=db,
        event_type=event_type,
        payload={
            "collaboration_uuid": collab.collaboration_uuid,
            "incident_id": collab.incident_id,
            "organization_id": collab.organization_id,
            "new_status": new_status_upper,
        },
        organization_id=collab.organization_id,
        incident_id=collab.incident_id,
        actor_id=acting_user_id,
    )

    db.commit()
    db.refresh(collab)
    return collab


def update_information_grants(
    db: Session,
    collaboration_id: int,
    acting_org_id: int,
    acting_user_id: int,
    scopes_to_grant: List[str],
    scopes_to_revoke: List[str],
) -> List[IncidentInformationGrant]:
    collab = db.query(IncidentAgencyCollaboration).filter(IncidentAgencyCollaboration.id == collaboration_id).first()
    if not collab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found.")

    all_scopes = set(scopes_to_grant) | set(scopes_to_revoke)
    invalid_scopes = all_scopes - VALID_SCOPES
    if invalid_scopes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid scopes: {list(invalid_scopes)}")

    # Grant scopes
    for scope_name in scopes_to_grant:
        grant = (
            db.query(IncidentInformationGrant)
            .filter(
                IncidentInformationGrant.collaboration_id == collab.id,
                IncidentInformationGrant.scope == scope_name,
            )
            .first()
        )
        if not grant:
            grant = IncidentInformationGrant(
                grant_uuid=str(uuid.uuid4()),
                collaboration_id=collab.id,
                scope=scope_name,
                is_granted=True,
                granted_by_user_id=acting_user_id,
                granted_at=utc_now(),
            )
            db.add(grant)
        else:
            grant.is_granted = True
            grant.revoked_at = None
            grant.granted_by_user_id = acting_user_id
            grant.granted_at = utc_now()

    # Revoke scopes
    for scope_name in scopes_to_revoke:
        grant = (
            db.query(IncidentInformationGrant)
            .filter(
                IncidentInformationGrant.collaboration_id == collab.id,
                IncidentInformationGrant.scope == scope_name,
            )
            .first()
        )
        if grant:
            grant.is_granted = False
            grant.revoked_at = utc_now()

    log_inter_agency_audit(
        db=db,
        incident_id=collab.incident_id,
        acting_org_id=acting_org_id,
        acting_user_id=acting_user_id,
        action_type="GRANTS_UPDATED",
        target_agency_id=collab.organization_id,
        details={"granted": scopes_to_grant, "revoked": scopes_to_revoke},
    )

    record_and_publish_event(
        db=db,
        event_type="inter_agency.grants.updated",
        payload={
            "collaboration_uuid": collab.collaboration_uuid,
            "incident_id": collab.incident_id,
            "organization_id": collab.organization_id,
            "granted": scopes_to_grant,
            "revoked": scopes_to_revoke,
        },
        organization_id=collab.organization_id,
        incident_id=collab.incident_id,
        actor_id=acting_user_id,
    )

    db.commit()

    return db.query(IncidentInformationGrant).filter(IncidentInformationGrant.collaboration_id == collab.id).all()
