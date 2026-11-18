"""
CareOn Milestone 9 — Conflict Detection and Resolution Engine.

Implements explicit conflict strategies across clinical observations,
mission state transitions, GPS telemetry, and hospital destination reassignments.
Never performs blind last-write-wins for emergency or clinical data.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    SyncConflict,
    SyncAuditEvent,
    DeviceRegistration,
    User,
    utc_now,
)

logger = logging.getLogger("careon.sync.conflict_engine")


class ConflictCategory:
    MISSION_STATE = "MISSION_STATE"
    CLINICAL = "CLINICAL"
    ASSIGNMENT = "ASSIGNMENT"
    TELEMETRY = "TELEMETRY"
    DESTINATION = "DESTINATION"


class ResolutionStatus:
    PENDING = "PENDING"
    RESOLVED_SERVER = "RESOLVED_SERVER"
    RESOLVED_CLIENT = "RESOLVED_CLIENT"
    DISCARDED = "DISCARDED"


def record_sync_conflict(
    db: Session,
    device: DeviceRegistration,
    user: User,
    action_uuid: str,
    conflict_category: str,
    reason: str,
    client_state: Dict[str, Any],
    server_state: Dict[str, Any],
    mission_id: Optional[int] = None,
    encounter_id: Optional[int] = None,
) -> SyncConflict:
    """
    Persist an explicit synchronization conflict.
    Provides structured data for operational dispatcher review or client reconciliation.
    """
    conflict_token = f"conf_{uuid.uuid4().hex[:16]}"
    now = utc_now()

    conflict = SyncConflict(
        conflict_token=conflict_token,
        action_uuid=action_uuid,
        device_id=device.id,
        user_id=user.id,
        mission_id=mission_id,
        encounter_id=encounter_id,
        conflict_category=conflict_category,
        reason=reason,
        client_state_json=json.dumps(client_state, default=str),
        server_state_json=json.dumps(server_state, default=str),
        resolution_status=ResolutionStatus.PENDING,
        created_at=now,
    )
    db.add(conflict)
    db.flush()

    audit = SyncAuditEvent(
        device_id=device.id,
        user_id=user.id,
        event_type="CONFLICT_DETECTED",
        details_json=json.dumps({
            "conflict_token": conflict_token,
            "action_uuid": action_uuid,
            "category": conflict_category,
            "reason": reason,
            "timestamp": now.isoformat(),
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(conflict)

    logger.warning(
        "Sync conflict recorded [%s]: %s (action=%s, device=%s)",
        conflict_category,
        reason,
        action_uuid,
        device.device_identifier,
    )
    return conflict


def reconcile_sync_conflict(
    db: Session,
    conflict_token: str,
    resolver_user: User,
    resolution: str,
    notes: Optional[str] = None,
) -> SyncConflict:
    """
    Reconcile a pending synchronization conflict.
    Permitted resolutions: RESOLVED_SERVER, RESOLVED_CLIENT, DISCARDED.
    """
    conflict = (
        db.query(SyncConflict)
        .filter(SyncConflict.conflict_token == conflict_token)
        .first()
    )
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conflict with token '{conflict_token}' not found.",
        )

    if conflict.resolution_status != ResolutionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conflict already resolved with status '{conflict.resolution_status}'.",
        )

    if resolution not in [
        ResolutionStatus.RESOLVED_SERVER,
        ResolutionStatus.RESOLVED_CLIENT,
        ResolutionStatus.DISCARDED,
    ]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid resolution '{resolution}'. Must be RESOLVED_SERVER, RESOLVED_CLIENT, or DISCARDED.",
        )

    now = utc_now()
    conflict.resolution_status = resolution
    conflict.resolution_notes = notes
    conflict.resolved_by_user_id = resolver_user.id
    conflict.resolved_at = now

    audit = SyncAuditEvent(
        device_id=conflict.device_id,
        user_id=resolver_user.id,
        event_type="CONFLICT_RESOLVED",
        details_json=json.dumps({
            "conflict_token": conflict_token,
            "resolution": resolution,
            "resolved_by": resolver_user.id,
            "notes": notes,
            "timestamp": now.isoformat(),
        }),
    )
    db.add(audit)
    db.commit()
    db.refresh(conflict)
    return conflict
