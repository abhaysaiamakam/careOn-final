"""
CareOn RBAC module.

Exports the most-used symbols for convenient one-line imports:

    from app.rbac import UserRole, Permission, require_permission
"""

from app.rbac.roles import (
    UserRole,
    Permission,
    ROLE_PERMISSIONS,
    ROLE_MIGRATION_MAP,
    get_permissions,
    has_permission,
)
from app.rbac.permissions import (
    require_permission,
    require_any_permission,
    require_all_permissions,
    check_incident_ownership,
    check_organization_scope,
)
from app.rbac.dependencies import (
    get_current_user_flexible,
    get_current_active_user,
    get_optional_user_flexible,
    require_role,
)

__all__ = [
    # roles
    "UserRole",
    "Permission",
    "ROLE_PERMISSIONS",
    "ROLE_MIGRATION_MAP",
    "get_permissions",
    "has_permission",
    # permissions
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
    "check_incident_ownership",
    "check_organization_scope",
    # dependencies
    "get_current_user_flexible",
    "get_current_active_user",
    "get_optional_user_flexible",
    "require_role",
]
