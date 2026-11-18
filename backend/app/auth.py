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
        if secret == INSECURE_DEFAULT_SECRET:
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
    """Create a tamper-evident signed token (Base64 JSON + HMAC-SHA256 signature)."""
    data = payload.copy()
    data["exp"] = int(time.time()) + TOKEN_EXPIRY_SECONDS
    encoded_payload = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8").rstrip("=")
    key = get_secret_key()
    signature = hmac.new(key.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{encoded_payload}.{signature}"


def decode_access_token(token: str) -> Optional[dict]:
    """Verify signature and expiration of access token."""
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
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
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
    return db.query(User).filter(User.id == payload["sub"]).first()
