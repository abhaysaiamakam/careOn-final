"""
CareOn RBAC — FastAPI dependency functions.

Provides flexible authentication that works with BOTH:
  • Legacy 2-segment HMAC tokens (from app.auth)
  • New PyJWT access tokens (from app.identity.jwt_handler)

The existing get_current_user / get_current_admin / get_optional_user in
auth.py are NOT touched; they continue to serve all existing routes unchanged.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.rbac.roles import UserRole, ROLE_MIGRATION_MAP

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_user_role(user: User) -> UserRole:
    """Coerce user.role (may be old string) to a UserRole enum value."""
    raw = getattr(user, "role", None) or "user"
    if raw in UserRole._value2member_map_:
        return UserRole(raw)
    return ROLE_MIGRATION_MAP.get(raw, UserRole.CITIZEN)


def _try_new_jwt(token: str) -> Optional[dict]:
    """Attempt to decode as a new PyJWT access token; returns payload or None."""
    try:
        from app.identity.jwt_handler import decode_access_token  # type: ignore
        return decode_access_token(token)
    except Exception:
        return None


def _try_legacy_hmac(token: str) -> Optional[dict]:
    """Attempt to decode as a legacy HMAC token; returns payload or None."""
    try:
        from app.auth import decode_access_token as _decode_legacy
        return _decode_legacy(token)
    except Exception:
        return None


def _load_user_from_payload(payload: dict, db: Session) -> Optional[User]:
    """Look up User by the 'sub' claim; return None if missing or inactive."""
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None

    user: Optional[User] = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    # Gracefully check is_active — column may not exist in legacy schema
    try:
        if not user.is_active:
            return None
    except AttributeError:
        pass  # Column not yet migrated; skip the check

    return user


# ---------------------------------------------------------------------------
# Primary flexible dependency
# ---------------------------------------------------------------------------

def get_current_user_flexible(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate using new JWT first, then fall back to legacy HMAC.

    Raises HTTP 401 if neither succeeds.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = _try_new_jwt(token) or _try_legacy_hmac(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = _load_user_from_payload(payload, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# Alias for callers that prefer the "active_user" naming convention
get_current_active_user = get_current_user_flexible


# ---------------------------------------------------------------------------
# Optional flexible dependency (does not raise on missing / bad token)
# ---------------------------------------------------------------------------

def get_optional_user_flexible(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user_flexible but returns None instead of raising 401."""
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    payload = _try_new_jwt(token) or _try_legacy_hmac(token)
    if not payload:
        return None

    return _load_user_from_payload(payload, db)


# ---------------------------------------------------------------------------
# Role-based dependency factory
# ---------------------------------------------------------------------------

def require_role(*roles: UserRole) -> Callable:
    """Return a FastAPI dependency that enforces the caller has one of *roles*.

    Accepts both new UserRole enum values and legacy role strings by normalising
    through _resolve_user_role.

    Usage::

        @router.get("/admin-only")
        def admin_view(user: User = Depends(require_role(UserRole.SUPER_ADMIN))):
            ...
    """
    role_set: set[UserRole] = set(roles)

    async def _dependency(
        user: User = Depends(get_current_user_flexible),
    ) -> User:
        effective_role = _resolve_user_role(user)
        if effective_role not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have the required role to access this resource.",
            )
        return user

    return _dependency
