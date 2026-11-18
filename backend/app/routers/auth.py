"""
auth.py — CareOn M2 Extended Authentication Router

Provides endpoints for:
  - Refresh token rotation (POST /api/auth/refresh)
  - Logout and token revocation (POST /api/auth/logout)
  - Password change with session revocation (POST /api/auth/change-password)
  - Password reset request & confirmation (POST /api/auth/reset-password/...)
"""

import time
import base64
import json
import hmac
import hashlib
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import (
    RefreshRequest,
    LogoutRequest,
    TokenPairResponse,
    UserResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.auth import verify_password, hash_password, get_secret_key
from app.rbac.dependencies import get_current_user_flexible
from app.identity.refresh_tokens import (
    rotate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
)
from app.identity.sessions import extract_device_hint
from app.rate_limiter import rate_limit

logger = logging.getLogger("careon.routers.auth")

router = APIRouter(prefix="/api/auth", tags=["Auth Extended"])


@router.post("/refresh", response_model=TokenPairResponse)
def refresh_token_endpoint(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("auth")),
):
    """
    Rotate a refresh token to obtain a fresh access token and a new refresh token.
    Enforces automatic family-based revocation if a previously used token is presented.
    """
    device_hint = extract_device_hint(request)
    result = rotate_refresh_token(db, payload.refresh_token, device_hint=device_hint)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_raw_refresh, new_access_token, token_record = result
    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user or (hasattr(user, "is_active") and not user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
        )

    db.commit()
    return TokenPairResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh,
        token_type="Bearer",
        expires_in=1800,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
def logout_endpoint(
    payload: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Revoke refresh tokens for the authenticated user.
    If a specific refresh_token is provided, only that token is revoked.
    Otherwise, all active refresh tokens for the user are invalidated.
    """
    if payload and payload.refresh_token:
        revoked = revoke_refresh_token(db, payload.refresh_token)
    else:
        revoked = revoke_all_user_tokens(db, current_user.id)

    audit = AuditLog(
        action="USER_LOGOUT",
        entity_type="User",
        entity_id=str(current_user.id),
        actor=current_user.email,
        details=f"User logged out. Revoked tokens count or status: {revoked}",
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": "Successfully logged out."}


@router.post("/change-password")
def change_password_endpoint(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("auth")),
):
    """
    Change user password after verifying current credentials.
    Automatically invalidates all existing refresh tokens across all devices.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password verification failed.",
        )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation do not match.",
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long.",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    # Revoke all existing sessions to enforce re-login with the new password
    revoked_count = revoke_all_user_tokens(db, current_user.id)

    audit = AuditLog(
        action="PASSWORD_CHANGED",
        entity_type="User",
        entity_id=str(current_user.id),
        actor=current_user.email,
        details=f"Password updated. Invalidated {revoked_count} active refresh tokens.",
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": "Password changed successfully. All sessions have been logged out."}


def _create_password_reset_token(user_id: int, email: str) -> str:
    """Create a tamper-evident 1-hour password reset token."""
    exp = int(time.time()) + 3600
    data = {"sub": user_id, "email": email, "exp": exp, "purpose": "pwd_reset"}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8").rstrip("=")
    key = get_secret_key()
    sig = hmac.new(key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def _verify_password_reset_token(token: str) -> Optional[dict]:
    """Verify password reset token signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        key = get_secret_key()
        expected = hmac.new(key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        rem = len(payload_b64) % 4
        padded = payload_b64 + ("=" * (4 - rem) if rem else "")
        data = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if data.get("exp", 0) < time.time() or data.get("purpose") != "pwd_reset":
            return None
        return data
    except Exception:
        return None


@router.post("/reset-password/request")
def request_password_reset(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("auth")),
):
    """
    Request a password reset link/token.
    Never discloses whether an email exists in the database to prevent account enumeration.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if user and user.is_active:
        reset_token = _create_password_reset_token(user.id, user.email)
        # In production this would send an email. For demo/API readiness, we record the audit log.
        audit = AuditLog(
            action="PASSWORD_RESET_REQUESTED",
            entity_type="User",
            entity_id=str(user.id),
            actor=payload.email,
            details=f"Password reset token issued for user {user.id}",
        )
        db.add(audit)
        db.commit()

    return {
        "status": "success",
        "message": "If this email address is registered, password reset instructions have been dispatched.",
    }


@router.post("/reset-password/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("auth")),
):
    """
    Complete password reset with a validated reset token.
    """
    token_data = _verify_password_reset_token(payload.token)
    if not token_data or "sub" not in token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    user = db.query(User).filter(User.id == token_data["sub"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    user.hashed_password = hash_password(payload.new_password)
    revoke_all_user_tokens(db, user.id)

    audit = AuditLog(
        action="PASSWORD_RESET_COMPLETED",
        entity_type="User",
        entity_id=str(user.id),
        actor=user.email,
        details="Password successfully reset via token confirmation.",
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": "Password reset completed successfully. You may now login."}
