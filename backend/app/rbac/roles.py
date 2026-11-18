"""
CareOn RBAC — Role and Permission definitions.

Roles follow a deny-by-default model: each role carries an explicit set of
permissions; anything not in the set is denied.

Legacy role strings ("user", "admin") are mapped to new roles via
ROLE_MIGRATION_MAP so that existing JWT payloads and DB rows keep working
during the M2 migration window.
"""

from enum import Enum


class UserRole(str, Enum):
    """Canonical role identifiers stored in JWT claims and (eventually) the DB."""

    CITIZEN = "citizen"
    DISPATCHER = "dispatcher"
    RESPONDER = "responder"
    HOSPITAL_STAFF = "hospital_staff"
    ORGANIZATION_ADMIN = "org_admin"
    SUPER_ADMIN = "super_admin"


# ---------------------------------------------------------------------------
# Legacy → new role migration map
# Maps old role string values (as stored in users.role) to their M2 equivalents.
# ---------------------------------------------------------------------------
ROLE_MIGRATION_MAP: dict[str, UserRole] = {
    "user": UserRole.CITIZEN,
    "admin": UserRole.SUPER_ADMIN,
}


class Permission(str, Enum):
    """Typed permission constants (format: resource:action)."""

    # Incidents
    INCIDENT_CREATE = "incident:create"
    INCIDENT_READ_OWN = "incident:read_own"
    INCIDENT_READ_OPERATIONAL = "incident:read_operational"
    INCIDENT_UPDATE = "incident:update"
    INCIDENT_CANCEL_OWN = "incident:cancel_own"
    INCIDENT_ASSIGN = "incident:assign"
    INCIDENT_VERIFY = "incident:verify"
    INCIDENT_PRIORITIZE = "incident:prioritize"
    INCIDENT_RESOLVE = "incident:resolve"
    # Resources
    RESOURCE_READ = "resource:read"
    RESOURCE_MANAGE = "resource:manage"
    # Responder
    RESPONDER_MISSION_READ = "responder:mission_read"
    RESPONDER_MISSION_UPDATE = "responder:mission_update"
    # Hospital
    HOSPITAL_READINESS_UPDATE = "hospital:readiness_update"
    HOSPITAL_INCOMING_PATIENT = "hospital:incoming_patient"
    # Handover
    HANDOVER_CREATE = "handover:create"
    HANDOVER_ACKNOWLEDGE = "handover:acknowledge"
    # Organization
    ORG_MANAGE = "organization:manage"
    # Users
    USERS_MANAGE = "users:manage"
    # Audit
    AUDIT_READ = "audit:read"
    # Platform
    PLATFORM_CONFIGURE = "platform:configure"
    # Tracking (public, no auth required — but rate limited)
    TRACKING_PUBLIC = "tracking:public"


# ---------------------------------------------------------------------------
# Role → permission mapping (deny by default)
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.CITIZEN: {
        Permission.INCIDENT_CREATE,
        Permission.INCIDENT_READ_OWN,
        Permission.INCIDENT_CANCEL_OWN,
        Permission.RESOURCE_READ,
        Permission.TRACKING_PUBLIC,
    },
    UserRole.DISPATCHER: {
        Permission.INCIDENT_CREATE,
        Permission.INCIDENT_READ_OWN,
        Permission.INCIDENT_READ_OPERATIONAL,
        Permission.INCIDENT_UPDATE,
        Permission.INCIDENT_CANCEL_OWN,
        Permission.INCIDENT_ASSIGN,
        Permission.INCIDENT_VERIFY,
        Permission.INCIDENT_PRIORITIZE,
        Permission.INCIDENT_RESOLVE,
        Permission.RESOURCE_READ,
        Permission.RESOURCE_MANAGE,
        Permission.RESPONDER_MISSION_READ,
        Permission.TRACKING_PUBLIC,
    },
    UserRole.RESPONDER: {
        Permission.INCIDENT_READ_OPERATIONAL,
        Permission.RESPONDER_MISSION_READ,
        Permission.RESPONDER_MISSION_UPDATE,
        Permission.RESOURCE_READ,
        Permission.TRACKING_PUBLIC,
    },
    UserRole.HOSPITAL_STAFF: {
        Permission.HOSPITAL_READINESS_UPDATE,
        Permission.HOSPITAL_INCOMING_PATIENT,
        Permission.HANDOVER_ACKNOWLEDGE,
        Permission.INCIDENT_READ_OPERATIONAL,
        Permission.TRACKING_PUBLIC,
    },
    UserRole.ORGANIZATION_ADMIN: {
        # All dispatcher permissions plus org management
        Permission.INCIDENT_CREATE,
        Permission.INCIDENT_READ_OWN,
        Permission.INCIDENT_READ_OPERATIONAL,
        Permission.INCIDENT_UPDATE,
        Permission.INCIDENT_CANCEL_OWN,
        Permission.INCIDENT_ASSIGN,
        Permission.INCIDENT_VERIFY,
        Permission.INCIDENT_PRIORITIZE,
        Permission.INCIDENT_RESOLVE,
        Permission.RESOURCE_READ,
        Permission.RESOURCE_MANAGE,
        Permission.RESPONDER_MISSION_READ,
        Permission.HOSPITAL_READINESS_UPDATE,
        Permission.HANDOVER_CREATE,
        Permission.HANDOVER_ACKNOWLEDGE,
        Permission.ORG_MANAGE,
        Permission.USERS_MANAGE,
        Permission.AUDIT_READ,
        Permission.TRACKING_PUBLIC,
    },
    # SUPER_ADMIN gets every permission defined in the enum
    UserRole.SUPER_ADMIN: set(Permission),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_permissions(role: "UserRole | str") -> set[Permission]:
    """Return the permission set for *role*, transparently mapping legacy strings.

    Unknown strings default to CITIZEN (safest fallback).
    """
    if isinstance(role, str) and role not in UserRole._value2member_map_:
        role = ROLE_MIGRATION_MAP.get(role, UserRole.CITIZEN)
    try:
        return ROLE_PERMISSIONS.get(UserRole(role), set())
    except (ValueError, KeyError):
        return set()


def has_permission(role: "UserRole | str", permission: Permission) -> bool:
    """Return True if *role* carries *permission*."""
    return permission in get_permissions(role)
