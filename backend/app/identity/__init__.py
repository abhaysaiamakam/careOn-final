"""
CareOn Identity Module — M2

Provides:
  - JWT access token creation and validation (jwt_handler)
  - Refresh token lifecycle and rotation (refresh_tokens)
  - Session helpers (sessions)
"""

from app.identity.jwt_handler import (
    create_access_token,
    decode_access_token,
    create_legacy_compat_token,
    decode_legacy_compat_token,
)
from app.identity.refresh_tokens import (
    generate_refresh_token,
    create_refresh_token_record,
    rotate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
)
from app.identity.sessions import (
    get_or_create_session_id,
    extract_device_hint,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "create_legacy_compat_token",
    "decode_legacy_compat_token",
    "generate_refresh_token",
    "create_refresh_token_record",
    "rotate_refresh_token",
    "revoke_refresh_token",
    "revoke_all_user_tokens",
    "get_or_create_session_id",
    "extract_device_hint",
]
