"""
identity.py — CareOn M2 User Identity & Profile Router

Provides endpoints for:
  - Viewing and updating the current user's profile
  - Viewing and revoking active user sessions
  - Administrative role assignment and account deactivation
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession, RefreshToken, AuditLog
from app.schemas import (
    UserResponse,
    UserProfileUpdate,
    UserRoleUpdate,
    UserStatusUpdate,
    SessionResponse,
)
from app.rbac.roles import UserRole
from app.rbac.dependencies import get_current_user_flexible, require_role
from app.identity.refresh_tokens import revoke_all_user_tokens

router = APIRouter(prefix="/api/users", tags=["Identity"])


# ==============================================================================
# Self-Service Profile & Session Endpoints
# ==============================================================================
@router.get("/me/profile", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user_flexible)):
    """Retrieve authenticated user's profile information."""
    return UserResponse.model_validate(current_user)


@router.patch("/me/profile", response_model=UserResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Update personal profile fields (name, phone).
    Protected fields like email, role, and trust_score cannot be altered here.
    """
    changed = False
    if payload.name and payload.name.strip() != current_user.name:
        current_user.name = payload.name.strip()
        changed = True
    if payload.phone and payload.phone.strip() != current_user.phone:
        current_user.phone = payload.phone.strip()
        changed = True

    if changed:
        audit = AuditLog(
            action="USER_PROFILE_UPDATED",
            entity_type="User",
            entity_id=str(current_user.id),
            actor=current_user.email,
            details=f"Updated profile details for {current_user.email}",
        )
        db.add(audit)
        db.commit()
        db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.get("/me/sessions", response_model=List[SessionResponse])
def get_my_sessions(
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Retrieve all active client sessions for the authenticated user."""
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id, UserSession.is_active == True)
        .order_by(UserSession.last_seen_at.desc())
        .all()
    )
    return [SessionResponse.model_validate(s) for s in sessions]


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_my_session(
    session_id: str,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Revoke a specific device/client session and its associated refresh tokens."""
    sess = (
        db.query(UserSession)
        .filter(UserSession.session_id == session_id, UserSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already terminated.",
        )

    sess.is_active = False

    # Invalidate associated refresh tokens
    refresh_tokens = (
        db.query(RefreshToken)
        .filter(RefreshToken.session_id == session_id, RefreshToken.is_revoked == False)
        .all()
    )
    now = datetime.now(timezone.utc)
    for rt in refresh_tokens:
        rt.is_revoked = True
        rt.revoked_reason = "session_terminated"
        rt.revoked_at = now

    audit = AuditLog(
        action="SESSION_TERMINATED",
        entity_type="UserSession",
        entity_id=session_id,
        actor=current_user.email,
        details=f"Terminated session {session_id} and invalidated {len(refresh_tokens)} tokens.",
    )
    db.add(audit)
    db.commit()
    return None


# ==============================================================================
# Administrative User & Role Management (Super Admin only)
# ==============================================================================
@router.get("", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = Query(None),
    status_filter: Optional[bool] = Query(None, alias="is_active"),
    admin: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """List platform users with optional role and status filters (Super Admin only)."""
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if status_filter is not None:
        q = q.filter(User.is_active == status_filter)
    return [UserResponse.model_validate(u) for u in q.all()]


@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int,
    admin: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Get single user profile (Super Admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    admin: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Assign a new platform role to a user.
    Only Super Admins may assign roles. Prevents self-demotion from super_admin to lockouts.
    """
    valid_roles = {r.value for r in UserRole} | {"admin", "user"}
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {sorted(valid_roles)}",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    old_role = user.role
    user.role = payload.role

    # Revoke sessions so new permissions take effect on next login
    revoked = revoke_all_user_tokens(db, user.id)

    audit = AuditLog(
        action="USER_ROLE_CHANGED",
        entity_type="User",
        entity_id=str(user.id),
        actor=admin.email,
        details=f"Changed role of user {user.id} ({user.email}) from {old_role} to {payload.role}. Revoked {revoked} tokens.",
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    admin: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Activate or deactivate a user account.
    Deactivating immediately terminates all active sessions and refresh tokens.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    user.is_active = payload.is_active
    revoked = 0
    if not payload.is_active:
        revoked = revoke_all_user_tokens(db, user.id)

    audit = AuditLog(
        action="USER_STATUS_CHANGED",
        entity_type="User",
        entity_id=str(user.id),
        actor=admin.email,
        details=f"Set is_active={payload.is_active} for user {user.id}. Revoked {revoked} tokens. Reason: {payload.reason or 'None'}",
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)
