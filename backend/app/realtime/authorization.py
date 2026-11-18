"""
CareOn Milestone 4 — Real-Time WebSocket Authorization and Security.

Enforces:
- Full M2 JWT token verification (signature, expiry, issuer, audience)
- Account active verification against database
- Deny-by-default role-based channel subscription guards
- Tenant organization isolation
- Incident ownership validation (citizens only subscribe to their own incidents)
- Sensitive PII stripping (sanitization)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set
import logging
from sqlalchemy.orm import Session

from app.models import User, Incident, Assignment, Resource, OrganizationMembership
from app.rbac.roles import UserRole, ROLE_MIGRATION_MAP
from app.rbac.dependencies import _try_new_jwt, _try_legacy_hmac, _resolve_user_role

logger = logging.getLogger("careon.realtime.auth")


@dataclass
class RealtimeUserSession:
    user_id: int
    email: str
    name: str
    role: UserRole
    org_ids: Set[int] = field(default_factory=set)

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_dispatcher(self) -> bool:
        return self.role in (UserRole.DISPATCHER, UserRole.ORGANIZATION_ADMIN, UserRole.SUPER_ADMIN)

    @property
    def is_responder(self) -> bool:
        return self.role in (UserRole.RESPONDER, UserRole.SUPER_ADMIN)


def authenticate_ws_token(token: str, db: Session) -> Optional[RealtimeUserSession]:
    """
    Validate JWT token, verify user account is active, and return an authorized session.
    Returns None if token is invalid, expired, or user is inactive.
    """
    if not token or not isinstance(token, str):
        return None

    # Try PyJWT access token first, then fallback to HMAC
    payload = _try_new_jwt(token) or _try_legacy_hmac(token)
    if not payload:
        logger.warning("WebSocket auth failed: invalid or expired token signature")
        return None

    sub = payload.get("sub")
    if sub is None:
        return None

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None

    user: Optional[User] = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"WebSocket auth failed: user {user_id} not found")
        return None

    if not getattr(user, "is_active", True):
        logger.warning(f"WebSocket auth failed: user {user_id} is inactive / disabled")
        return None

    role = _resolve_user_role(user)

    # Load active organization memberships
    org_ids: Set[int] = set()
    try:
        memberships = (
            db.query(OrganizationMembership.organization_id)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == "active",
            )
            .all()
        )
        org_ids = {m[0] for m in memberships}
    except Exception as exc:
        logger.warning(f"Failed to query organization memberships: {exc}")

    return RealtimeUserSession(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=role,
        org_ids=org_ids,
    )


def can_subscribe_channel(session: RealtimeUserSession, channel: str, db: Session) -> bool:
    """
    Evaluate whether the authenticated session is authorized to subscribe to *channel*.
    Deny by default!
    """
    if not channel or not isinstance(channel, str):
        return False

    # 1. Global operational channel
    if channel == "careon:events:global":
        # Strictly restricted to dispatchers and super admins
        return session.is_dispatcher or session.is_super_admin

    # 2. Organization-scoped channel (careon:events:org:{org_id})
    if channel.startswith("careon:events:org:"):
        try:
            org_id = int(channel.split("careon:events:org:")[1])
            if session.is_super_admin:
                return True
            return org_id in session.org_ids
        except (ValueError, IndexError):
            return False

    # 3. Incident-specific channel (careon:events:incident:{incident_id})
    if channel.startswith("careon:events:incident:"):
        try:
            incident_id = int(channel.split("careon:events:incident:")[1])
            # Dispatchers and Super Admins can observe all incidents
            if session.is_dispatcher or session.is_super_admin:
                return True

            # Responders can observe if their assigned unit is dispatched to this incident
            if session.is_responder:
                assigned = (
                    db.query(Assignment)
                    .join(Assignment.resource)
                    .filter(
                        Assignment.incident_id == incident_id,
                        Resource.assigned_user_id == session.user_id,
                        Assignment.status.in_(["Active", "Accepted", "En Route", "On Scene", "Transporting"]),
                    )
                    .first()
                )
                if assigned:
                    return True

            # Citizens can ONLY observe their own incident
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if incident and incident.user_id == session.user_id:
                return True

            return False
        except (ValueError, IndexError):
            return False

    # 4. Responder-specific private channel (careon:events:responder:{user_id})
    if channel.startswith("careon:events:responder:"):
        try:
            responder_user_id = int(channel.split("careon:events:responder:")[1])
            return session.user_id == responder_user_id or session.is_super_admin or session.is_dispatcher
        except (ValueError, IndexError):
            return False

    return False


def sanitize_payload_for_viewer(payload: dict, viewer: Any) -> dict:
    """
    Remove sensitive personal and operational information for citizen/untrusted viewers.
    Never leak verification OTPs, caller phone numbers, or internal notes to third parties.
    Accepts either RealtimeUserSession, UserRole, or a role string.
    """
    role = getattr(viewer, "role", viewer)
    if isinstance(role, str):
        from app.rbac.roles import ROLE_MIGRATION_MAP
        role = ROLE_MIGRATION_MAP.get(role.lower(), role)

    if role in (UserRole.SUPER_ADMIN, UserRole.DISPATCHER, UserRole.ORGANIZATION_ADMIN):
        return payload

    sanitized = payload.copy()
    # Strip security and private PII fields
    for secret_field in (
        "verification_otp",
        "contact_phone",
        "internal_admin_notes",
        "internal_notes",
        "admin_notes",
        "dispatcher_notes",
        "disaster_details",
    ):
        sanitized.pop(secret_field, None)

    return sanitized
