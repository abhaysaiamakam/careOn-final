"""
CareOn RBAC — Permission-checking utilities.

Provides FastAPI dependency factories and inline guard helpers that enforce
fine-grained permission control on top of the role definitions in roles.py.

Design principles
-----------------
- Deny by default: if a permission is not explicitly granted, access is denied.
- Operational roles (DISPATCHER, RESPONDER, HOSPITAL_STAFF, ORGANIZATION_ADMIN,
  SUPER_ADMIN) can read all incidents; CITIZEN can only read their own.
- Organization scope is enforced at the row level for all non-SUPER_ADMIN users.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.rbac.roles import Permission, UserRole, get_permissions, ROLE_MIGRATION_MAP
from app.rbac.dependencies import get_current_user_flexible, _resolve_user_role


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _user_has_permission(user: User, permission: Permission) -> bool:
    """Return True if *user*'s effective role includes *permission*."""
    role = _resolve_user_role(user)
    return permission in get_permissions(role)


# ---------------------------------------------------------------------------
# Single-permission dependency factory
# ---------------------------------------------------------------------------

def require_permission(permission: Permission) -> Callable:
    """Return a FastAPI dependency that enforces *permission* on the caller.

    Usage::

        @router.post("/incidents")
        def create_incident(
            payload: IncidentCreate,
            user: User = Depends(require_permission(Permission.INCIDENT_CREATE)),
        ):
            ...
    """
    async def _dependency(
        user: User = Depends(get_current_user_flexible),
    ) -> User:
        if not _user_has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required.",
            )
        return user

    return _dependency


# ---------------------------------------------------------------------------
# Multi-permission dependency factories
# ---------------------------------------------------------------------------

def require_any_permission(*permissions: Permission) -> Callable:
    """Return a dependency that passes if the user has ANY of *permissions* (OR).

    Usage::

        Depends(require_any_permission(
            Permission.INCIDENT_READ_OWN,
            Permission.INCIDENT_READ_OPERATIONAL,
        ))
    """
    perm_set = set(permissions)

    async def _dependency(
        user: User = Depends(get_current_user_flexible),
    ) -> User:
        user_perms = get_permissions(_resolve_user_role(user))
        if not perm_set.intersection(user_perms):
            names = ", ".join(f"'{p.value}'" for p in permissions)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"At least one of the following permissions is required: {names}.",
            )
        return user

    return _dependency


def require_all_permissions(*permissions: Permission) -> Callable:
    """Return a dependency that passes only if the user has ALL *permissions* (AND).

    Usage::

        Depends(require_all_permissions(
            Permission.INCIDENT_ASSIGN,
            Permission.RESOURCE_MANAGE,
        ))
    """
    perm_set = set(permissions)

    async def _dependency(
        user: User = Depends(get_current_user_flexible),
    ) -> User:
        user_perms = get_permissions(_resolve_user_role(user))
        missing = perm_set - user_perms
        if missing:
            names = ", ".join(f"'{p.value}'" for p in missing)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {names}.",
            )
        return user

    return _dependency


# ---------------------------------------------------------------------------
# Inline guard helpers (called inside route bodies, not as Depends)
# ---------------------------------------------------------------------------

# Roles that can read all incidents (not just their own)
_OPERATIONAL_ROLES: frozenset[UserRole] = frozenset({
    UserRole.DISPATCHER,
    UserRole.RESPONDER,
    UserRole.HOSPITAL_STAFF,
    UserRole.ORGANIZATION_ADMIN,
    UserRole.SUPER_ADMIN,
})


def check_incident_ownership(incident, user: User) -> None:
    """Raise HTTP 403 if *user* does not own *incident* and lacks operational access.

    Parameters
    ----------
    incident:
        Any object with a ``user_id`` attribute (the SQLAlchemy Incident model).
    user:
        The authenticated User ORM instance.
    """
    effective_role = _resolve_user_role(user)
    if effective_role in _OPERATIONAL_ROLES:
        return  # Operational roles can see all incidents
    if getattr(incident, "user_id", None) != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this incident.",
        )


def check_organization_scope(user: User, org_id: int, db: Session) -> None:
    """Raise HTTP 403 if *user* is not a member of *org_id* (unless SUPER_ADMIN).

    Uses a lightweight membership query so it works even before the full ORM
    relationship is migrated.

    Parameters
    ----------
    user:
        Authenticated User ORM instance.
    org_id:
        The organization ID being accessed.
    db:
        Active SQLAlchemy Session.
    """
    effective_role = _resolve_user_role(user)
    if effective_role == UserRole.SUPER_ADMIN:
        return  # Super-admins have platform-wide scope

    # Lazy import to avoid circular import at module load time
    try:
        from app.models import OrganizationMembership  # type: ignore
        membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == "active",
            )
            .first()
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this organization.",
            )
    except ImportError:
        # OrganizationMembership not yet available (migration pending); deny by default
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization scope check unavailable.",
        )
