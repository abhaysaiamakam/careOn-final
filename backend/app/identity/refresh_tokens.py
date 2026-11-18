"""
refresh_tokens.py — CareOn M2 Identity Module

Handles refresh token lifecycle:
  - Secure generation (raw token returned once, only hash stored)
  - Creation with family tracking for reuse detection
  - Rotation with theft-detection (family revocation on reuse)
  - Revocation (single token and logout-all)
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

REFRESH_TOKEN_EXPIRE_DAYS = 30


# ---------------------------------------------------------------------------
# Dataclasses (pure Python, not SQLAlchemy)
# ---------------------------------------------------------------------------


@dataclass
class RefreshTokenCreate:
    """Input parameters for creating a refresh token record."""

    user_id: int
    session_id: Optional[str] = None
    device_hint: str = ""


@dataclass
class RefreshTokenResult:
    """Result returned from refresh token operations."""

    raw_token: str          # Return ONCE to the client; never persisted
    token_hash: str         # SHA-256 hex; what is stored in the DB
    family_id: str          # Opaque family identifier for reuse detection
    expires_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(raw: str) -> str:
    """Return the SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """
    Generate a cryptographically secure refresh token.

    Returns:
        (raw_token, token_hash) where raw_token is returned to the client
        and token_hash (SHA-256 hex) is stored in the database.
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = _sha256_hex(raw_token)
    return raw_token, token_hash


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------


def create_refresh_token_record(
    db: Session,
    user_id: int,
    session_id: Optional[str],
    device_hint: str = "",
) -> tuple[str, "RefreshToken"]:  # noqa: F821  (forward ref; avoids circular import)
    """
    Create a new refresh token for a user.

    The raw token is returned ONCE and never stored.  Only the SHA-256 hash
    is persisted.

    Args:
        db:          SQLAlchemy session.
        user_id:     Owner's DB id.
        session_id:  Optional session UUID (from X-Session-ID header).
        device_hint: Truncated User-Agent string (max 200 chars).

    Returns:
        (raw_token, RefreshToken ORM instance) with the ORM flushed to the DB.
    """
    from app.models import RefreshToken  # local import to avoid circular deps

    raw_token, token_hash = generate_refresh_token()
    family_id = secrets.token_hex(16)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id,
        session_id=session_id,
        device_hint=device_hint[:200] if device_hint else "",
        is_revoked=False,
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()
    return raw_token, record


def rotate_refresh_token(
    db: Session,
    raw_token: str,
    device_hint: str = "",
) -> Optional[tuple[str, str, "RefreshToken"]]:  # noqa: F821
    """
    Rotate a refresh token.

    Implements the RFC 6749 / OAuth 2.0 token rotation pattern with
    family-based theft detection:

    1. Hash incoming raw_token.
    2. Look up RefreshToken by hash → None if not found.
    3. If revoked → REUSE DETECTED: revoke entire family + audit log → None.
    4. If expired → revoke + None.
    5. Revoke old token (reason: "rotated").
    6. Create new RefreshToken in the same family with a new hash.
    7. Mint a new access token.
    8. Return (new_raw_token, new_access_token_str, new_orm).

    Returns:
        (new_raw_token, new_access_token_str, new_RefreshToken) or None.
    """
    from app.models import AuditLog, RefreshToken, User  # local import
    from app.identity.jwt_handler import create_access_token  # local import

    incoming_hash = _sha256_hex(raw_token)
    now = datetime.now(timezone.utc)

    record: Optional[RefreshToken] = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == incoming_hash)
        .first()
    )

    if record is None:
        logger.warning("rotate_refresh_token: token not found (never issued or already cleaned up)")
        return None

    # --- Reuse detection: token already revoked ---
    if record.is_revoked:
        logger.warning(
            "REFRESH TOKEN REUSE DETECTED for family %s user_id=%s — revoking entire family",
            record.family_id,
            record.user_id,
        )
        # Revoke every token in this family
        family_tokens = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == record.family_id,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
            .all()
        )
        for ft in family_tokens:
            ft.is_revoked = True
            ft.revoked_reason = "reuse_detected"
            ft.revoked_at = now

        # Emit audit log
        audit = AuditLog(
            action="refresh_token_reuse_detected",
            entity_type="refresh_token",
            entity_id=str(record.user_id),
            actor=f"user:{record.user_id}",
            details=(
                f"Family {record.family_id} fully revoked due to token reuse. "
                f"Revoked {len(family_tokens)} active tokens."
            ),
        )
        db.add(audit)
        db.flush()
        return None

    # --- Expiry check ---
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        record.is_revoked = True
        record.revoked_reason = "expired"
        record.revoked_at = now
        db.flush()
        logger.debug("rotate_refresh_token: token expired for user_id=%s", record.user_id)
        return None

    # --- Rotate: revoke old, mint new ---
    record.is_revoked = True
    record.revoked_reason = "rotated"
    record.revoked_at = now

    # Look up user for new access token claims
    user: Optional[User] = db.query(User).filter(User.id == record.user_id).first()
    if user is None:
        logger.error("rotate_refresh_token: user %s not found", record.user_id)
        return None

    new_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    new_raw_token, new_hash = generate_refresh_token()

    new_record = RefreshToken(
        user_id=record.user_id,
        token_hash=new_hash,
        family_id=record.family_id,          # keep the same family
        session_id=record.session_id,
        device_hint=device_hint[:200] if device_hint else record.device_hint,
        is_revoked=False,
        expires_at=new_expires_at,
    )
    db.add(new_record)

    new_access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    db.flush()
    return new_raw_token, new_access_token, new_record


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    """
    Revoke a single refresh token by its raw value.

    Returns:
        True if the token was found and revoked, False otherwise.
    """
    from app.models import RefreshToken  # local import

    token_hash = _sha256_hex(raw_token)
    now = datetime.now(timezone.utc)

    record: Optional[RefreshToken] = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.is_revoked == False)  # noqa: E712
        .first()
    )
    if record is None:
        return False

    record.is_revoked = True
    record.revoked_reason = "logout"
    record.revoked_at = now
    db.flush()
    return True


def revoke_all_user_tokens(db: Session, user_id: int) -> int:
    """
    Revoke ALL active refresh tokens for a given user (logout-all).

    Returns:
        Count of tokens revoked.
    """
    from app.models import RefreshToken  # local import

    now = datetime.now(timezone.utc)
    active_tokens = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)  # noqa: E712
        .all()
    )
    for token in active_tokens:
        token.is_revoked = True
        token.revoked_reason = "logout"
        token.revoked_at = now

    db.flush()
    return len(active_tokens)
