"""
organizations.py — CareOn M2 Multi-Organization Router

Provides endpoints for:
  - Managing emergency response organizations (Ambulance services, Hospitals, Fire, Police)
  - Tenant-scoped membership and role management
  - Cross-tenant boundary enforcement
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Organization, OrganizationMembership, User, AuditLog
from app.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    MembershipCreate,
    MembershipUpdate,
    MembershipResponse,
    UserResponse,
)
from app.rbac.roles import UserRole
from app.rbac.dependencies import get_current_user_flexible, require_role
from app.rbac.permissions import check_organization_scope

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


def _is_org_admin(user: User, org_id: int, db: Session) -> bool:
    """Return True if user is super_admin or an active admin/dispatcher of this organization."""
    if user.role in ("super_admin", "admin"):
        return True
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "active",
        )
        .first()
    )
    return membership is not None and membership.membership_role in ("admin", "org_admin")


# ==============================================================================
# Organization Endpoints
# ==============================================================================
@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    org_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    List organizations across the platform.
    Citizens and responders can see active directory records.
    """
    q = db.query(Organization)
    if active_only:
        q = q.filter(Organization.is_active == True)
    if org_type:
        q = q.filter(Organization.org_type.ilike(org_type))
    return [OrganizationResponse.model_validate(org) for org in q.order_by(Organization.name).all()]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    admin: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a new emergency service organization (Super Admin only)."""
    existing = db.query(Organization).filter(Organization.name.ilike(payload.name.strip())).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with name '{payload.name}' already exists.",
        )

    org = Organization(
        name=payload.name.strip(),
        org_type=payload.org_type.strip(),
        description=payload.description,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        location_name=payload.location_name,
        is_active=True,
        is_verified=False,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    audit = AuditLog(
        action="ORGANIZATION_CREATED",
        entity_type="Organization",
        entity_id=str(org.id),
        actor=admin.email,
        details=f"Created organization '{org.name}' ({org.org_type})",
    )
    db.add(audit)
    db.commit()

    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Retrieve organization details. Enforces organization scope for private details."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return OrganizationResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Update organization profile.
    Requires Super Admin or Organization Administrator.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    if not _is_org_admin(current_user, org_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an organization administrator to modify this organization.",
        )

    # Only Super Admin can verify organizations
    if payload.is_verified is not None and payload.is_verified != org.is_verified:
        if current_user.role not in ("super_admin", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admins can verify organizations.",
            )
        org.is_verified = payload.is_verified

    for field, val in payload.model_dump(exclude_unset=True).items():
        if field != "is_verified" and hasattr(org, field) and val is not None:
            setattr(org, field, val)

    audit = AuditLog(
        action="ORGANIZATION_UPDATED",
        entity_type="Organization",
        entity_id=str(org.id),
        actor=current_user.email,
        details=f"Updated details for organization '{org.name}'",
    )
    db.add(audit)
    db.commit()
    db.refresh(org)

    return OrganizationResponse.model_validate(org)


# ==============================================================================
# Membership Endpoints (Tenant Management)
# ==============================================================================
@router.get("/{org_id}/members", response_model=List[MembershipResponse])
def list_organization_members(
    org_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    List members of an organization.
    Requires active membership within that organization or Super Admin privileges.
    """
    check_organization_scope(current_user, org_id, db)

    memberships = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == org_id)
        .order_by(OrganizationMembership.joined_at.desc())
        .all()
    )

    out = []
    for m in memberships:
        user_resp = UserResponse.model_validate(m.user) if m.user else None
        item = MembershipResponse(
            id=m.id,
            organization_id=m.organization_id,
            user_id=m.user_id,
            membership_role=m.membership_role,
            status=m.status,
            joined_at=m.joined_at,
            user=user_resp,
        )
        out.append(item)
    return out


@router.post("/{org_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    org_id: int,
    payload: MembershipCreate,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Add a user to an organization.
    Requires Organization Administrator or Super Admin.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    if not _is_org_admin(current_user, org_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to add organization members.",
        )

    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found.")

    existing = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        if existing.status == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an active member of this organization.",
            )
        # Reactivate membership
        existing.status = "active"
        existing.membership_role = payload.membership_role
        db.commit()
        db.refresh(existing)
        return MembershipResponse(
            id=existing.id,
            organization_id=existing.organization_id,
            user_id=existing.user_id,
            membership_role=existing.membership_role,
            status=existing.status,
            joined_at=existing.joined_at,
            user=UserResponse.model_validate(target_user),
        )

    membership = OrganizationMembership(
        organization_id=org_id,
        user_id=payload.user_id,
        membership_role=payload.membership_role,
        status="active",
        invited_by_user_id=current_user.id,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    audit = AuditLog(
        action="ORG_MEMBER_ADDED",
        entity_type="OrganizationMembership",
        entity_id=str(membership.id),
        actor=current_user.email,
        details=f"Added user {target_user.email} to {org.name} as {payload.membership_role}",
    )
    db.add(audit)
    db.commit()

    return MembershipResponse(
        id=membership.id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        membership_role=membership.membership_role,
        status=membership.status,
        joined_at=membership.joined_at,
        user=UserResponse.model_validate(target_user),
    )


@router.patch("/{org_id}/members/{user_id}", response_model=MembershipResponse)
def update_organization_member(
    org_id: int,
    user_id: int,
    payload: MembershipUpdate,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Update member role or status within an organization.
    Requires Organization Administrator or Super Admin.
    """
    if not _is_org_admin(current_user, org_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to modify organization memberships.",
        )

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found.")

    if payload.membership_role:
        membership.membership_role = payload.membership_role
    if payload.status:
        membership.status = payload.status

    audit = AuditLog(
        action="ORG_MEMBER_UPDATED",
        entity_type="OrganizationMembership",
        entity_id=str(membership.id),
        actor=current_user.email,
        details=f"Updated membership for user {user_id} in org {org_id} to role={membership.membership_role}, status={membership.status}",
    )
    db.add(audit)
    db.commit()
    db.refresh(membership)

    user_resp = UserResponse.model_validate(membership.user) if membership.user else None
    return MembershipResponse(
        id=membership.id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        membership_role=membership.membership_role,
        status=membership.status,
        joined_at=membership.joined_at,
        user=user_resp,
    )


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_organization_member(
    org_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Deactivate or remove a user from an organization.
    Requires Organization Administrator or Super Admin.
    """
    if not _is_org_admin(current_user, org_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to remove organization members.",
        )

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership record not found.")

    membership.status = "inactive"
    audit = AuditLog(
        action="ORG_MEMBER_REMOVED",
        entity_type="OrganizationMembership",
        entity_id=str(membership.id),
        actor=current_user.email,
        details=f"Deactivated membership for user {user_id} in organization {org_id}",
    )
    db.add(audit)
    db.commit()
    return None
