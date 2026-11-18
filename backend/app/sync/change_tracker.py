"""
CareOn Milestone 9 — Sync Change Tracker (Download Server Changes).

Generates authorized operational and clinical updates for responder devices
using stable, deterministic, server-generated cursors.
Never exposes data outside the authenticated user's authorization scope.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models import (
    DeviceRegistration,
    User,
    Assignment,
    Incident,
    Resource,
    HospitalFacility,
    EmergencyEncounter,
    ClinicalTimelineEvent,
    DigitalHandoverRecord,
    utc_now,
)
from app.schemas import (
    SyncDownloadResponse,
    SyncDownloadChangeItem,
)
from app.sync.device_manager import get_verified_device

logger = logging.getLogger("careon.sync.change_tracker")


def ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_cursor_to_datetime(cursor_str: Optional[str]) -> datetime:
    """Parse string cursor to UTC datetime with microsecond precision."""
    if not cursor_str or cursor_str == "0":
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        val = int(cursor_str)
        # Support microsecond cursors (> 1e14) as well as millisecond cursors
        if val > 1e14:
            return datetime.fromtimestamp(val / 1_000_000.0, tz=timezone.utc)
        return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
    except Exception:
        try:
            return ensure_utc(datetime.fromisoformat(cursor_str))
        except Exception:
            return datetime.fromtimestamp(0, tz=timezone.utc)


def format_datetime_to_cursor(dt: datetime) -> str:
    """Format UTC datetime into deterministic monotonic microsecond cursor string."""
    dt = ensure_utc(dt)
    return str(int(dt.timestamp() * 1_000_000))


def get_changes_since_cursor(
    db: Session,
    user: User,
    device_identifier: str,
    since_cursor: Optional[str] = "0",
    limit: int = 50,
) -> SyncDownloadResponse:
    """
    Query and return authorized changes since the device's acknowledged cursor.
    """
    device = get_verified_device(db, device_identifier, user)
    cursor_dt = parse_cursor_to_datetime(since_cursor)
    now = utc_now()

    # Find responder's resources
    resources = db.query(Resource).filter(Resource.assigned_user_id == user.id).all()
    resource_ids = [r.id for r in resources]

    # Query 1: Assignments / Missions
    assignment_q = (
        db.query(Assignment)
        .filter(
            or_(
                Assignment.resource_id.in_(resource_ids),
                Assignment.notes.ilike(f"%{user.id}%"),
            )
        )
        .filter(Assignment.assigned_at > cursor_dt)
        .order_by(Assignment.assigned_at.asc())
        .limit(limit)
    )
    assignments = assignment_q.all()

    changes: List[SyncDownloadChangeItem] = []
    latest_seen_dt = cursor_dt

    for a in assignments:
        a_time = ensure_utc(a.acknowledged_at or a.assigned_at or now)
        if a_time > latest_seen_dt:
            latest_seen_dt = a_time
        changes.append(
            SyncDownloadChangeItem(
                change_id=f"mission_{a.id}_{int(a_time.timestamp())}",
                entity_type="mission",
                entity_id=a.id,
                operation="update",
                timestamp=a_time,
                data={
                    "assignment_id": a.id,
                    "incident_id": a.incident_id,
                    "resource_id": a.resource_id,
                    "status": a.status,
                    "notes": a.notes,
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                    "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                },
            )
        )

    # Active mission incident IDs
    active_incident_ids = [a.incident_id for a in assignments]
    if not active_incident_ids:
        # Check all assignments belonging to responder
        all_assigns = db.query(Assignment).filter(Assignment.resource_id.in_(resource_ids)).all()
        active_incident_ids = [a.incident_id for a in all_assigns]

    if active_incident_ids:
        # Query 2: Incident updates
        incidents = (
            db.query(Incident)
            .filter(Incident.id.in_(active_incident_ids))
            .filter(Incident.updated_at > cursor_dt)
            .order_by(Incident.updated_at.asc())
            .limit(limit)
            .all()
        )
        for inc in incidents:
            inc_time = ensure_utc(inc.updated_at or inc.created_at)
            if inc_time > latest_seen_dt:
                latest_seen_dt = inc_time
            changes.append(
                SyncDownloadChangeItem(
                    change_id=f"incident_{inc.id}_{int(inc_time.timestamp())}",
                    entity_type="incident",
                    entity_id=inc.id,
                    operation="update",
                    timestamp=inc_time,
                    data={
                        "incident_id": inc.id,
                        "incident_code": inc.incident_code,
                        "category": inc.category,
                        "title": inc.title,
                        "description": inc.description,
                        "priority": inc.priority,
                        "status": inc.status,
                        "location_name": inc.location_name,
                        "latitude": inc.latitude,
                        "longitude": inc.longitude,
                    },
                )
            )

        # Query 3: Encounters
        encounters = (
            db.query(EmergencyEncounter)
            .filter(EmergencyEncounter.incident_id.in_(active_incident_ids))
            .filter(EmergencyEncounter.updated_at > cursor_dt)
            .order_by(EmergencyEncounter.updated_at.asc())
            .limit(limit)
            .all()
        )
        for enc in encounters:
            enc_time = ensure_utc(enc.updated_at or enc.started_at)
            if enc_time > latest_seen_dt:
                latest_seen_dt = enc_time
            changes.append(
                SyncDownloadChangeItem(
                    change_id=f"encounter_{enc.id}_{int(enc_time.timestamp())}",
                    entity_type="encounter",
                    entity_id=enc.id,
                    operation="update",
                    timestamp=enc_time,
                    data={
                        "encounter_id": enc.id,
                        "encounter_code": enc.encounter_code,
                        "patient_id": enc.patient_id,
                        "status": enc.status,
                        "chief_complaint": enc.chief_complaint,
                        "initial_acuity": enc.initial_acuity,
                        "receiving_facility_id": enc.receiving_facility_id,
                    },
                )
            )

        # Query 4: Handovers
        encounter_ids = [enc.id for enc in encounters]
        if encounter_ids:
            handovers = (
                db.query(DigitalHandoverRecord)
                .filter(DigitalHandoverRecord.encounter_id.in_(encounter_ids))
                .filter(DigitalHandoverRecord.updated_at > cursor_dt)
                .order_by(DigitalHandoverRecord.updated_at.asc())
                .limit(limit)
                .all()
            )
            for h in handovers:
                h_time = ensure_utc(h.updated_at or h.created_at)
                if h_time > latest_seen_dt:
                    latest_seen_dt = h_time
                changes.append(
                    SyncDownloadChangeItem(
                        change_id=f"handover_{h.id}_{int(h_time.timestamp())}",
                        entity_type="handover",
                        entity_id=h.id,
                        operation="update",
                        timestamp=h_time,
                        data={
                            "handover_id": h.id,
                            "handover_token": h.handover_token,
                            "encounter_id": h.encounter_id,
                            "facility_id": h.facility_id,
                            "status": h.status,
                            "version": h.version,
                            "is_final": h.is_final,
                        },
                    )
                )

    # Sort all changes by timestamp ascending
    changes.sort(key=lambda c: c.timestamp)
    if len(changes) > limit:
        changes = changes[:limit]
        has_more = True
    else:
        has_more = False

    if changes:
        next_cursor = format_datetime_to_cursor(changes[-1].timestamp)
    else:
        next_cursor = since_cursor or "0"

    return SyncDownloadResponse(
        device_id=device.device_identifier,
        previous_cursor=since_cursor or "0",
        next_cursor=next_cursor,
        has_more=has_more,
        changes_count=len(changes),
        changes=changes,
        server_time=now,
    )
