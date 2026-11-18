"""
CareOn Milestone 3 — Super Admin & Operations Router.

Strictly protected: ONLY users with effective role SUPER_ADMIN can access.
No frontend-only security.

Endpoints:
- GET   /api/admin/system-health    → DB, PostGIS, Redis, table metrics
- GET   /api/admin/audit-logs       → Centralized audit log inspector with filters
- GET   /api/admin/users            → User directory with role and status management
- PATCH /api/admin/users/{id}/role  → Assign/change user role
- PATCH /api/admin/users/{id}/status→ Activate/deactivate user account
- GET   /api/admin/analytics        → Platform-wide operational overview
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db, is_postgres
from app.models import (
    User,
    Incident,
    Resource,
    Assignment,
    Organization,
    OrganizationMembership,
    AuditLog,
    HospitalReadiness,
    utc_now,
)
from app.rbac.roles import UserRole
from app.rbac.dependencies import require_role
from app.redis_client import get_redis_client
from app.schemas import (
    SystemHealthResponse,
    AuditLogQueryResponse,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)

router = APIRouter(prefix="/api/admin", tags=["Super Admin"])


@router.get("/system-health", response_model=SystemHealthResponse)
def get_system_health(
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Live infrastructure health check verifying PostgreSQL connection,
    PostGIS spatial functions, Redis cache, and operational metrics.
    """
    # 1. Database check
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    # 2. PostGIS check
    postgis_ok = False
    if is_postgres():
        try:
            res = db.execute(text("SELECT PostGIS_Version()")).scalar()
            postgis_ok = bool(res)
        except Exception:
            postgis_ok = False
    else:
        postgis_ok = False

    # 3. Redis check
    redis_connected = False
    try:
        r = get_redis_client()
        redis_connected = r.ping()
    except Exception:
        redis_connected = False

    # 4. Operational Counts
    active_incidents = (
        db.query(func.count(Incident.id))
        .filter(Incident.status.notin_(["Resolved", "Cancelled", "Rejected"]))
        .scalar()
        or 0
    )
    available_resources = (
        db.query(func.count(Resource.id))
        .filter(Resource.status == "Available")
        .scalar()
        or 0
    )
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_orgs = db.query(func.count(Organization.id)).scalar() or 0
    audit_count = db.query(func.count(AuditLog.id)).scalar() or 0

    overall_status = "healthy" if (db_connected and (not is_postgres() or postgis_ok)) else "degraded"

    return SystemHealthResponse(
        status=overall_status,
        database_connected=db_connected,
        postgis_available=postgis_ok,
        redis_connected=redis_connected,
        active_incidents=active_incidents,
        available_resources=available_resources,
        total_users=total_users,
        total_organizations=total_orgs,
        audit_log_count=audit_count,
        timestamp=utc_now(),
    )


@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action string"),
    actor: Optional[str] = Query(None, description="Filter by actor name"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Query platform-wide audit logs with filtering and pagination."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if actor:
        query = query.filter(AuditLog.actor.ilike(f"%{actor}%"))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    total = query.count()
    items = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            AuditLogQueryResponse(
                id=log.id,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                actor=log.actor,
                details=log.details,
                created_at=log.created_at,
            )
            for log in items
        ],
    }


@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """List platform users with optional role and status filters."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    return query.order_by(User.id.asc()).offset(offset).limit(limit).all()


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Change the system-wide role of a user."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = target_user.role
    target_user.role = payload.role.lower()

    audit = AuditLog(
        action="USER_ROLE_CHANGE",
        entity_type="user",
        entity_id=str(target_user.id),
        actor=user.name,
        details=f"Changed role of {target_user.email} from '{old_role}' to '{target_user.role}'",
    )
    db.add(audit)
    db.commit()
    db.refresh(target_user)
    return target_user


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Activate or deactivate a user account."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if target_user.id == user.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super Admins cannot deactivate their own account.",
        )

    target_user.is_active = payload.is_active
    audit = AuditLog(
        action="USER_STATUS_CHANGE",
        entity_type="user",
        entity_id=str(target_user.id),
        actor=user.name,
        details=f"Account status set to active={payload.is_active}. Reason: {payload.reason or 'N/A'}",
    )
    db.add(audit)
    db.commit()
    db.refresh(target_user)
    return target_user


@router.get("/operations-summary")
def get_operational_analytics(
    user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """High-level platform-wide analytics for operations leadership."""
    total_incidents = db.query(func.count(Incident.id)).scalar() or 0
    active_incidents = (
        db.query(func.count(Incident.id))
        .filter(Incident.status.notin_(["Resolved", "Cancelled", "Rejected"]))
        .scalar()
        or 0
    )
    critical_incidents = (
        db.query(func.count(Incident.id))
        .filter(
            Incident.priority == "Critical",
            Incident.status.notin_(["Resolved", "Cancelled", "Rejected"]),
        )
        .scalar()
        or 0
    )

    fleet_total = db.query(func.count(Resource.id)).scalar() or 0
    fleet_available = (
        db.query(func.count(Resource.id))
        .filter(Resource.status == "Available")
        .scalar()
        or 0
    )
    fleet_assigned = (
        db.query(func.count(Resource.id))
        .filter(Resource.status.in_(["Assigned", "Busy"]))
        .scalar()
        or 0
    )

    divert_count = (
        db.query(func.count(HospitalReadiness.id))
        .filter(HospitalReadiness.divert_status == True)
        .scalar()
        or 0
    )

    return {
        "incidents": {
            "total": total_incidents,
            "active": active_incidents,
            "critical": critical_incidents,
        },
        "fleet": {
            "total": fleet_total,
            "available": fleet_available,
            "deployed": fleet_assigned,
        },
        "hospitals": {
            "on_divert": divert_count,
        },
        "timestamp": utc_now().isoformat(),
    }
