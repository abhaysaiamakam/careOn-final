"""
CareOn Milestone 7 — Hospital Diversion Management & Resilient Caching.

Features:
- Diversion states:
    OPEN (open to all emergencies)
    PARTIAL_DIVERSION (capability-specific, e.g. CT scanner down, trauma diverted)
    FULL_DIVERSION (all incoming transports diverted)
    CLOSED (facility emergency department closed)
    EMERGENCY_ONLY (only life-threats accepted)
- PostgreSQL authoritative persistence in HospitalDiversionLog & HospitalFacility
- Backward compatibility sync with HospitalReadiness.divert_status
- Sub-millisecond Redis diversion caching with safe fallback on Redis outage
- Real-time Outbox event emission: hospital.diversion_changed
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    HospitalFacility,
    HospitalDiversionLog,
    HospitalReadiness,
    User,
    utc_now,
)
from app.redis_client import get_redis_client
from app.realtime.event_models import (
    EventTypes,
    get_org_channel,
    get_global_channel,
)
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.hospital_ops.diversion")


class DiversionStatus:
    OPEN = "open"
    PARTIAL_DIVERSION = "partial_diversion"
    FULL_DIVERSION = "full_diversion"
    CLOSED = "closed"
    EMERGENCY_ONLY = "emergency_only"


class DiversionType:
    TRAUMA = "trauma"
    PEDIATRIC = "pediatric"
    CT_DOWN = "ct_down"
    ED_SATURATION = "ed_saturation"
    STAFFING = "staffing"
    GENERAL = "general"


def get_facility_diversion_cache_key(facility_id: int) -> str:
    return f"careon:hospital:facility:{facility_id}:diversion"


def get_facility_diversion_status(facility_id: int, db: Session) -> Dict[str, Any]:
    """
    Retrieve diversion status for a facility.
    Checks Redis cache first; falls back safely to PostgreSQL.
    """
    cache_key = get_facility_diversion_cache_key(facility_id)
    r = get_redis_client()

    if r:
        try:
            cached_data = r.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as exc:
            logger.debug("Redis diversion cache read failed: %s", exc)

    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise ValueError(f"Hospital facility {facility_id} not found")

    # Fetch latest diversion log
    latest_log = (
        db.query(HospitalDiversionLog)
        .filter(HospitalDiversionLog.facility_id == facility_id)
        .order_by(HospitalDiversionLog.created_at.desc())
        .first()
    )

    status = facility.operating_status
    reason = latest_log.reason if latest_log else None
    diversion_type = latest_log.diversion_type if latest_log else None
    effective_from = latest_log.effective_from.isoformat() if latest_log and latest_log.effective_from else utc_now().isoformat()
    effective_until = latest_log.effective_until.isoformat() if latest_log and latest_log.effective_until else None

    result = {
        "facility_id": facility.id,
        "facility_name": facility.name,
        "organization_id": facility.organization_id,
        "operating_status": status,
        "is_diverted": status in (DiversionStatus.FULL_DIVERSION, DiversionStatus.PARTIAL_DIVERSION, DiversionStatus.CLOSED),
        "diversion_type": diversion_type,
        "reason": reason,
        "effective_from": effective_from,
        "effective_until": effective_until,
    }

    # Populate cache
    if r:
        try:
            r.set(cache_key, json.dumps(result), ex=300)
        except Exception as exc:
            logger.debug("Redis cache write failed: %s", exc)

    return result


def set_facility_diversion_status(
    db: Session,
    facility_id: int,
    new_status: str,
    reason: str,
    diversion_type: Optional[str] = None,
    effective_until: Optional[datetime] = None,
    user: Optional[User] = None,
) -> Dict[str, Any]:
    """
    Mutate facility diversion status.
    Records immutable audit row in HospitalDiversionLog, updates HospitalFacility,
    synchronizes backward-compatible HospitalReadiness, invalidates Redis, and broadcasts outbox event.
    """
    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise ValueError(f"Hospital facility {facility_id} not found")

    norm_status = new_status.strip().lower()
    valid_statuses = (
        DiversionStatus.OPEN,
        DiversionStatus.PARTIAL_DIVERSION,
        DiversionStatus.FULL_DIVERSION,
        DiversionStatus.CLOSED,
        DiversionStatus.EMERGENCY_ONLY,
    )
    if norm_status not in valid_statuses:
        raise ValueError(f"Invalid diversion status '{new_status}'. Allowed: {valid_statuses}")

    if not reason or len(reason.strip()) < 3:
        raise ValueError("A clear clinical or operational reason is mandatory when updating diversion status")

    previous_status = facility.operating_status
    facility.operating_status = norm_status
    now = utc_now()

    # Create diversion log audit
    log = HospitalDiversionLog(
        facility_id=facility.id,
        previous_status=previous_status,
        new_status=norm_status,
        diversion_type=diversion_type,
        reason=reason.strip(),
        effective_from=now,
        effective_until=effective_until,
        authorized_by_user_id=user.id if user else None,
        created_at=now,
    )
    db.add(log)

    # Sync backwards-compatible HospitalReadiness record if exists for this organization
    readiness = (
        db.query(HospitalReadiness)
        .filter(HospitalReadiness.organization_id == facility.organization_id)
        .first()
    )
    if readiness:
        readiness.divert_status = norm_status in (DiversionStatus.FULL_DIVERSION, DiversionStatus.CLOSED)
        readiness.divert_reason = reason.strip()
        readiness.updated_at = now
        if user:
            readiness.updated_by_user_id = user.id

    db.commit()

    # Invalidate Redis cache
    r = get_redis_client()
    if r:
        try:
            r.delete(get_facility_diversion_cache_key(facility_id))
            r.delete(f"careon:hospital:diversion:{facility.organization_id}")
        except Exception as exc:
            logger.debug("Redis cache invalidation failed: %s", exc)

    # Publish real-time event
    payload = {
        "facility_id": facility.id,
        "facility_name": facility.name,
        "organization_id": facility.organization_id,
        "previous_status": previous_status,
        "new_status": norm_status,
        "diversion_type": diversion_type,
        "reason": reason,
        "effective_from": now.isoformat(),
        "effective_until": effective_until.isoformat() if effective_until else None,
        "authorized_by": user.name if user else "System",
    }
    record_and_publish_event(
        db=db,
        event_type="hospital.diversion_changed",
        channel=get_org_channel(facility.organization_id),
        payload=payload,
        actor_id=user.id if user else None,
        organization_id=facility.organization_id,
    )
    record_and_publish_event(
        db=db,
        event_type="hospital.diversion_changed",
        channel=get_global_channel(),
        payload=payload,
        actor_id=user.id if user else None,
        organization_id=facility.organization_id,
    )
    db.commit()

    return {
        "facility_id": facility.id,
        "operating_status": norm_status,
        "is_diverted": norm_status in (DiversionStatus.FULL_DIVERSION, DiversionStatus.PARTIAL_DIVERSION, DiversionStatus.CLOSED),
        "reason": reason,
        "updated_at": now.isoformat(),
    }
