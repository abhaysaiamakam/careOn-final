"""
CareOn Milestone 7 — Dynamic Hospital Capacity & Safe Concurrency Engine.

Features:
- Structured capacity categories (er_beds, trauma_bays, icu_beds, ventilators, etc.)
- Five explicit capacity confidence states:
    VERIFIED_CURRENT (<= 15 min)
    REPORTED_UNVERIFIED (<= 60 min)
    AGING (1 to 3 hours)
    STALE (> 3 hours)
    UNKNOWN (no record or unverified)
- Strict validation:
    Non-negative values
    occupied + reserved + unavailable <= total capacity
- Atomic, concurrency-safe capacity reservation (SELECT ... FOR UPDATE)
- Expiry and reconciliation sweeper
- Outbox event publication (hospital.capacity_updated, hospital.capacity_reserved, hospital.capacity_released)
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    HospitalFacility,
    HospitalCapacity,
    HospitalCapacityReservation,
    User,
    Incident,
    utc_now,
)
from app.realtime.event_models import (
    EventTypes,
    get_org_channel,
    get_global_channel,
)
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.hospital_ops.capacity")


class CapacityCategory:
    ER_BEDS = "er_beds"
    TRAUMA_BAYS = "trauma_bays"
    ICU_BEDS = "icu_beds"
    CRITICAL_CARE_BEDS = "critical_care_beds"
    VENTILATORS = "ventilators"
    OXYGEN_BEDS = "oxygen_beds"
    SPECIALISTS = "specialists"


class CapacityFreshnessStatus:
    VERIFIED_CURRENT = "verified_current"        # <= 15 min
    REPORTED_UNVERIFIED = "reported_unverified"  # <= 60 min
    AGING = "aging"                              # 1 to 3 hours
    STALE = "stale"                              # > 3 hours
    UNKNOWN = "unknown"                          # Not recorded


# Standard freshness thresholds in seconds
VERIFIED_CURRENT_MAX_AGE_SEC = 900     # 15 minutes
REPORTED_UNVERIFIED_MAX_AGE_SEC = 3600 # 60 minutes
AGING_MAX_AGE_SEC = 10800              # 3 hours


class CapacityValidationError(ValueError):
    """Raised when capacity inputs violate physical or mathematical constraints."""
    pass


class InsufficientCapacityError(ValueError):
    """Raised when an atomic capacity reservation cannot be fulfilled due to lack of available beds."""
    pass


def calculate_capacity_freshness(last_updated: Optional[datetime], server_time: Optional[datetime] = None) -> str:
    """Classifies capacity confidence tier based on reporting latency."""
    if not last_updated:
        return CapacityFreshnessStatus.UNKNOWN

    now = server_time or utc_now()
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_seconds = max(0.0, (now - last_updated).total_seconds())

    if age_seconds <= VERIFIED_CURRENT_MAX_AGE_SEC:
        return CapacityFreshnessStatus.VERIFIED_CURRENT
    elif age_seconds <= REPORTED_UNVERIFIED_MAX_AGE_SEC:
        return CapacityFreshnessStatus.REPORTED_UNVERIFIED
    elif age_seconds <= AGING_MAX_AGE_SEC:
        return CapacityFreshnessStatus.AGING
    else:
        return CapacityFreshnessStatus.STALE


def update_facility_capacity(
    db: Session,
    facility_id: int,
    category: str,
    total: int,
    occupied: int,
    unavailable: int = 0,
    reporting_source: str = "staff_manual",
    user: Optional[User] = None,
    notes: Optional[str] = None,
) -> HospitalCapacity:
    """
    Updates capacity for a specific category within a hospital facility.
    Validates capacity invariants and updates the freshness classification.
    """
    # 1. Non-negative constraints
    if total < 0 or occupied < 0 or unavailable < 0:
        raise CapacityValidationError(
            f"Capacity values cannot be negative: total={total}, occupied={occupied}, unavailable={unavailable}"
        )

    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise ValueError(f"Hospital facility {facility_id} not found")

    # 2. Concurrency-safe lock for update
    capacity_row = (
        db.query(HospitalCapacity)
        .filter(
            HospitalCapacity.facility_id == facility_id,
            HospitalCapacity.category == category,
        )
        .with_for_update()
        .first()
    )

    current_reserved = capacity_row.reserved_capacity if capacity_row else 0
    now = utc_now()

    # 3. Total capacity invariant
    if (occupied + current_reserved + unavailable) > total:
        raise CapacityValidationError(
            f"Configured total capacity ({total}) is less than sum of occupied ({occupied}), "
            f"currently reserved ({current_reserved}), and unavailable ({unavailable}) capacity"
        )

    if not capacity_row:
        capacity_row = HospitalCapacity(
            facility_id=facility_id,
            category=category,
            total_capacity=total,
            occupied_capacity=occupied,
            reserved_capacity=0,
            unavailable_capacity=unavailable,
            reporting_source=reporting_source,
            verification_status=CapacityFreshnessStatus.VERIFIED_CURRENT,
            notes=notes,
            last_updated=now,
            updated_by_user_id=user.id if user else None,
        )
        db.add(capacity_row)
    else:
        capacity_row.total_capacity = total
        capacity_row.occupied_capacity = occupied
        capacity_row.unavailable_capacity = unavailable
        capacity_row.reporting_source = reporting_source
        capacity_row.verification_status = CapacityFreshnessStatus.VERIFIED_CURRENT
        capacity_row.notes = notes
        capacity_row.last_updated = now
        if user:
            capacity_row.updated_by_user_id = user.id

    facility.last_verified_at = now
    db.commit()
    db.refresh(capacity_row)

    # Publish real-time capacity update via Transactional Outbox
    payload = {
        "facility_id": facility_id,
        "facility_code": facility.facility_code,
        "organization_id": facility.organization_id,
        "category": category,
        "total_capacity": capacity_row.total_capacity,
        "occupied_capacity": capacity_row.occupied_capacity,
        "reserved_capacity": capacity_row.reserved_capacity,
        "unavailable_capacity": capacity_row.unavailable_capacity,
        "available_capacity": capacity_row.available_capacity,
        "verification_status": capacity_row.verification_status,
        "last_updated": capacity_row.last_updated.isoformat(),
    }
    record_and_publish_event(
        db=db,
        event_type="hospital.capacity_updated",
        channel=get_org_channel(facility.organization_id),
        payload=payload,
        actor_id=user.id if user else None,
        organization_id=facility.organization_id,
    )
    db.commit()

    return capacity_row


def reserve_facility_capacity(
    db: Session,
    facility_id: int,
    incident_id: int,
    assignment_id: Optional[int],
    category: str = CapacityCategory.ER_BEDS,
    quantity: int = 1,
    expires_in_seconds: int = 1800,  # 30 minutes default reservation window
    user: Optional[User] = None,
) -> HospitalCapacityReservation:
    """
    Atomically reserves capacity for an incoming emergency case.
    Uses SELECT ... FOR UPDATE to prevent overbooking races.
    """
    if quantity <= 0:
        raise CapacityValidationError("Reservation quantity must be at least 1")

    facility = db.query(HospitalFacility).filter(HospitalFacility.id == facility_id).first()
    if not facility:
        raise ValueError(f"Hospital facility {facility_id} not found")

    # Lock capacity row for atomic reservation
    capacity_row = (
        db.query(HospitalCapacity)
        .filter(
            HospitalCapacity.facility_id == facility_id,
            HospitalCapacity.category == category,
        )
        .with_for_update()
        .first()
    )

    if not capacity_row:
        raise InsufficientCapacityError(
            f"Capacity category '{category}' is not configured for facility '{facility.name}'"
        )

    # Check available capacity
    available = capacity_row.available_capacity
    if available < quantity:
        raise InsufficientCapacityError(
            f"Insufficient available capacity for category '{category}' at facility '{facility.name}'. "
            f"Requested: {quantity}, Available: {available}"
        )

    # Mutate reserved capacity
    capacity_row.reserved_capacity += quantity
    now = utc_now()
    expires_at = now + timedelta(seconds=expires_in_seconds)
    token = str(uuid.uuid4())

    reservation = HospitalCapacityReservation(
        reservation_token=token,
        facility_id=facility_id,
        incident_id=incident_id,
        assignment_id=assignment_id,
        category=category,
        quantity=quantity,
        status="active",
        expires_at=expires_at,
        created_at=now,
        created_by_user_id=user.id if user else None,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    # Emit real-time event
    payload = {
        "reservation_token": token,
        "facility_id": facility_id,
        "facility_name": facility.name,
        "incident_id": incident_id,
        "assignment_id": assignment_id,
        "category": category,
        "quantity": quantity,
        "expires_at": expires_at.isoformat(),
        "remaining_available": capacity_row.available_capacity,
    }
    record_and_publish_event(
        db=db,
        event_type="hospital.capacity_reserved",
        channel=get_org_channel(facility.organization_id),
        payload=payload,
        actor_id=user.id if user else None,
        incident_id=incident_id,
        organization_id=facility.organization_id,
    )
    db.commit()

    return reservation


def release_capacity_reservation(
    db: Session,
    reservation_token: str,
    reason: str = "released",
    user: Optional[User] = None,
) -> bool:
    """
    Releases a previously active capacity reservation.
    Decrements reserved capacity atomically and records release metadata.
    """
    reservation = (
        db.query(HospitalCapacityReservation)
        .filter(HospitalCapacityReservation.reservation_token == reservation_token)
        .first()
    )
    if not reservation:
        return False

    if reservation.status != "active":
        logger.info("Reservation %s is already %s", reservation_token, reservation.status)
        return False

    # Lock capacity row
    capacity_row = (
        db.query(HospitalCapacity)
        .filter(
            HospitalCapacity.facility_id == reservation.facility_id,
            HospitalCapacity.category == reservation.category,
        )
        .with_for_update()
        .first()
    )

    if capacity_row:
        capacity_row.reserved_capacity = max(0, capacity_row.reserved_capacity - reservation.quantity)

    now = utc_now()
    reservation.status = reason
    reservation.released_at = now
    reservation.release_reason = reason
    db.commit()

    facility = reservation.facility
    org_id = facility.organization_id if facility else None

    # Emit event
    payload = {
        "reservation_token": reservation_token,
        "facility_id": reservation.facility_id,
        "category": reservation.category,
        "quantity": reservation.quantity,
        "status": reason,
        "released_at": now.isoformat(),
        "remaining_available": capacity_row.available_capacity if capacity_row else None,
    }
    if org_id:
        record_and_publish_event(
            db=db,
            event_type="hospital.capacity_released",
            channel=get_org_channel(org_id),
            payload=payload,
            actor_id=user.id if user else None,
            incident_id=reservation.incident_id,
            organization_id=org_id,
        )
        db.commit()

    return True


def sweep_expired_reservations(db: Session) -> List[HospitalCapacityReservation]:
    """
    Sweeps and reconciles expired reservations that were not explicitly fulfilled or released.
    Reclaims reserved beds without corrupting capacity states.
    """
    now = utc_now()
    expired = (
        db.query(HospitalCapacityReservation)
        .filter(
            HospitalCapacityReservation.status == "active",
            HospitalCapacityReservation.expires_at <= now,
        )
        .all()
    )

    reclaimed: List[HospitalCapacityReservation] = []
    for res in expired:
        success = release_capacity_reservation(db, res.reservation_token, reason="expired")
        if success:
            reclaimed.append(res)

    return reclaimed


def get_facility_capacity_summary(db: Session, facility_id: int) -> Dict[str, Any]:
    """Retrieves multi-category capacity summary and overall confidence for a facility."""
    capacities = (
        db.query(HospitalCapacity)
        .filter(HospitalCapacity.facility_id == facility_id)
        .all()
    )

    now = utc_now()
    categories_data: Dict[str, Any] = {}
    freshest_timestamp: Optional[datetime] = None

    for cap in capacities:
        status = calculate_capacity_freshness(cap.last_updated, now)
        cap.verification_status = status  # sync status
        categories_data[cap.category] = {
            "total": cap.total_capacity,
            "occupied": cap.occupied_capacity,
            "reserved": cap.reserved_capacity,
            "unavailable": cap.unavailable_capacity,
            "available": cap.available_capacity,
            "verification_status": status,
            "last_updated": cap.last_updated.isoformat() if cap.last_updated else None,
            "reporting_source": cap.reporting_source,
        }
        if cap.last_updated:
            if not freshest_timestamp or cap.last_updated > freshest_timestamp:
                freshest_timestamp = cap.last_updated

    overall_freshness = calculate_capacity_freshness(freshest_timestamp, now) if freshest_timestamp else CapacityFreshnessStatus.UNKNOWN

    return {
        "facility_id": facility_id,
        "overall_freshness": overall_freshness,
        "last_verified_at": freshest_timestamp.isoformat() if freshest_timestamp else None,
        "categories": categories_data,
    }
