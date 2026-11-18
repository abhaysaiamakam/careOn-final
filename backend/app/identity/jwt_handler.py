"""
jwt_handler.py — CareOn M2 Identity Module

Handles creation and validation of HS256 JWT access tokens, plus a legacy
compatibility shim that transparently handles both old HMAC tokens (from auth.py)
and new JWT tokens during the zero-downtime transition window.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALGORITHM = "HS256"
ALGORITHM_ALLOWLIST = ["HS256"]
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ISSUER = "careon-platform"
AUDIENCE = "careon-clients"

# Re-use the same secret key resolution logic from auth.py so both token
# kinds are signed with the same key.
_INSECURE_DEFAULT_SECRET = "careon-super-secret-key-2026-demo"
_DEV_FALLBACK_SECRET = "careon-dev-only-secret-key-not-for-production"


def _get_jwt_secret() -> str:
    """Return the signing secret, mirroring auth.py's key resolution."""
    secret = os.getenv("CAREON_SECRET_KEY")
    return secret if secret else _DEV_FALLBACK_SECRET


# ---------------------------------------------------------------------------
# Access token creation
# ---------------------------------------------------------------------------


def create_access_token(
    user_id: int | str,
    email: str,
    role: str,
    org_ids: list[int] = [],
    extra_claims: dict[str, Any] = {},
) -> str:
    """
    Create a signed HS256 JWT access token.

    Claims included: sub, email, role, org_ids, iss, aud, iat, exp, type.
    No sensitive PII beyond email (no phone, no password hash).

    Args:
        user_id:     The user's integer DB id (stored as string in ``sub``).
        email:       The user's email address.
        role:        The user's role string (e.g. "user", "admin").
        org_ids:     Optional list of organisation IDs the user belongs to.
        extra_claims: Additional claims merged into the payload.

    Returns:
        Signed JWT string.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "org_ids": list(org_ids),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": exp,
        "type": "access",
        **extra_claims,
    }

    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Validate and decode a CareOn JWT access token.

    Validates: signature, algorithm allowlist, issuer, audience, expiry, and
    that ``type == "access"``.

    Returns:
        The decoded payload dict on success, or ``None`` on any failure.
        Never raises to the caller.
    """
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=ALGORITHM_ALLOWLIST,
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["exp", "iat", "sub", "type"]},
        )
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT access token expired")
        return None
    except jwt.InvalidAlgorithmError:
        logger.warning("JWT: algorithm not in allowlist")
        return None
    except jwt.InvalidIssuerError:
        logger.warning("JWT: invalid issuer")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("JWT: invalid audience")
        return None
    except Exception as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Legacy compatibility wrappers
# ---------------------------------------------------------------------------


def create_legacy_compat_token(user_id: int | str, email: str, role: str) -> str:
    """
    Thin wrapper around create_access_token for use by existing endpoints
    during the HMAC → JWT transition.  Emits a full JWT with no org_ids.
    """
    return create_access_token(user_id, email, role, org_ids=[], extra_claims={})


def decode_legacy_compat_token(token: str) -> Optional[dict]:
    """
    Zero-downtime compatibility decoder.

    1. Try new JWT (decode_access_token).
    2. If that fails, try the existing HMAC decoder from auth.py.
    3. Return a unified payload: {"sub": int, "email": str, "role": str}
       or None if both decoders fail.

    This keeps existing sessions alive until their 7-day HMAC expiry
    without forcing any re-login.
    """
    # --- Try new JWT first ---
    new_payload = decode_access_token(token)
    if new_payload is not None:
        return {
            "sub": int(new_payload["sub"]),
            "email": new_payload.get("email", ""),
            "role": new_payload.get("role", "user"),
        }

    # --- Fall back to legacy HMAC token ---
    try:
        from app.auth import decode_access_token as _legacy_decode  # noqa: PLC0415

        legacy_payload = _legacy_decode(token)
        if legacy_payload is not None and "sub" in legacy_payload:
            return {
                "sub": int(legacy_payload["sub"]),
                "email": legacy_payload.get("email", ""),
                "role": legacy_payload.get("role", "user"),
            }
    except Exception as exc:
        logger.debug("Legacy HMAC decode failed: %s", exc)

    return None
