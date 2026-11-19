import os
import hashlib
import hmac
import json
import base64
import time
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

INSECURE_DEFAULT_SECRET = "careon-super-secret-key-2026-demo"
DEV_FALLBACK_SECRET = "careon-dev-only-secret-key-not-for-production"
KNOWN_INSECURE_SECRETS = {
    INSECURE_DEFAULT_SECRET,
    DEV_FALLBACK_SECRET,
    "careon_dev_secret_key_long_random_string_2026",
    "change_me_to_a_long_random_secret_in_production",
    "secret",
    "password",
    "admin123",
}
TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7 days


def validate_and_get_secret_key(environment: Optional[str] = None, secret_override: Optional[str] = None) -> str:
    """
    Validate and return the secret key for token signing.
    Strictly forbids missing or insecure default keys in production environments.
    """
    env = (environment if environment is not None else os.getenv("CAREON_ENV", os.getenv("ENVIRONMENT", "development"))).lower()
    is_prod = env in ("production", "prod")
    secret = secret_override if secret_override is not None else os.getenv("CAREON_SECRET_KEY")

    if is_prod:
        if not secret:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: CAREON_SECRET_KEY environment variable must be set in production."
            )
        if secret in KNOWN_INSECURE_SECRETS:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: The known default demo secret key is strictly forbidden in production."
            )
        if len(secret) < 32:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: CAREON_SECRET_KEY must be at least 32 characters in production."
            )
        return secret

    if secret:
        return secret
    return DEV_FALLBACK_SECRET


def get_secret_key() -> str:
    return validate_and_get_secret_key()


SECRET_KEY = get_secret_key()

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"{salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored salt$hash string."""
    try:
        salt_hex, key_hex = hashed_password.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


def create_access_token(payload: dict) -> str:
    """Create an RFC 7519 HS256 JWT access token via app.identity.jwt_handler."""
    from app.identity.jwt_handler import create_access_token as _jwt_create_token
    user_id = payload.get("sub", "")
    email = payload.get("email", "")
    role = payload.get("role", "user")
    org_ids = payload.get("org_ids", [])
    extra = {k: v for k, v in payload.items() if k not in ("sub", "email", "role", "org_ids", "exp", "iat", "iss", "aud", "type")}
    return _jwt_create_token(user_id=user_id, email=email, role=role, org_ids=org_ids, extra_claims=extra)


def decode_access_token(token: str) -> Optional[dict]:
    """Verify signature and expiration. Supports new PyJWT tokens first, then legacy HMAC tokens."""
    # 1. Try PyJWT
    try:
        from app.identity.jwt_handler import decode_access_token as _jwt_decode
        payload = _jwt_decode(token)
        if payload and "sub" in payload:
            return {
                "sub": int(payload["sub"]) if str(payload["sub"]).isdigit() else payload["sub"],
                "email": payload.get("email", ""),
                "role": payload.get("role", "user"),
                "org_ids": payload.get("org_ids", []),
                "exp": payload.get("exp"),
            }
    except Exception:
        pass

    # 2. Fall back to legacy 2-segment HMAC
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        encoded_payload, signature = parts
        key = get_secret_key()
        expected_sig = hmac.new(key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        # Add padding back if necessary
        rem = len(encoded_payload) % 4
        padded = encoded_payload + ("=" * (4 - rem) if rem else "")
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
        )
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this resource.",
        )
    return current_user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials or not credentials.credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user and hasattr(user, "is_active") and not user.is_active:
        return None
    return user
