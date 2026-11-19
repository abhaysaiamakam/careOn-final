"""
CareOn Milestone 9 — Offline Synchronization REST API Router (/api/sync/v1).

Provides versioned endpoints for:
- Device installation registration and verification
- Device revocation
- Batch upload of queued offline responder actions
- Download of authorized server changes using stable cursors
- Reliable acknowledgement and cursor management
- Conflict retrieval and operational reconciliation
"""

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, DeviceRegistration, SyncConflict, utc_now
from app.auth import get_current_user, get_current_admin
from app.schemas import (
    DeviceSyncRegisterRequest,
    DeviceSyncResponse,
    DeviceRevokeRequest,
    SyncUploadBatchRequest,
    SyncUploadBatchResponse,
    SyncDownloadRequest,
    SyncDownloadResponse,
    SyncAckRequest,
    SyncAckResponse,
    SyncConflictResponse,
    SyncConflictReconcileRequest,
)
from app.sync import (
    register_or_update_device,
    get_verified_device,
    revoke_device,
    advance_device_cursor,
    process_sync_batch,
    get_changes_since_cursor,
    reconcile_sync_conflict,
    run_sync_recovery_cycle,
)

router = APIRouter(prefix="/api/sync/v1", tags=["Offline Synchronization (M9)"])


# ==============================================================================
# Device Registration & Lifecycle
# ==============================================================================

@router.post("/devices/register", response_model=DeviceSyncResponse, status_code=status.HTTP_200_OK)
def register_device_endpoint(
    payload: DeviceSyncRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register or update a responder field device installation.
    Binds the device to the authenticated user and initializes sync cursor.
    """
    device = register_or_update_device(db, current_user, payload)
    return device


@router.get("/devices/{device_id}", response_model=DeviceSyncResponse)
def get_device_endpoint(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve device registration details, active state, and current sync cursor.
    """
    device = get_verified_device(db, device_id, current_user)
    return device


@router.post("/devices/{device_id}/revoke", response_model=DeviceSyncResponse)
def revoke_device_endpoint(
    device_id: str,
    payload: DeviceRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revoke a device installation. Revoked devices are permanently barred from syncing.
    """
    device = revoke_device(db, device_id, current_user, payload.reason)
    return device


# ==============================================================================
# Batch Upload Synchronization
# ==============================================================================

@router.post("/upload", response_model=SyncUploadBatchResponse, status_code=status.HTTP_200_OK)
@router.post("/batch", response_model=SyncUploadBatchResponse, status_code=status.HTTP_200_OK)
def upload_sync_batch_endpoint(
    payload: SyncUploadBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a batch of queued actions recorded by an offline responder device.
    Supports partial batch completion: failures in individual actions do not abort valid actions.
    Enforces idempotency and non-destructive clinical appending.
    """
    return process_sync_batch(db, current_user, payload)


# ==============================================================================
# Download Synchronization Changes
# ==============================================================================

@router.post("/download", response_model=SyncDownloadResponse)
def download_sync_changes_endpoint(
    payload: SyncDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve authorized changes since the device's acknowledged cursor.
    Returns assigned mission updates, incident context, encounters, and handover status.
    """
    return get_changes_since_cursor(
        db=db,
        user=current_user,
        device_identifier=payload.device_id,
        since_cursor=payload.since_cursor,
        limit=payload.limit,
    )


# ==============================================================================
# Acknowledgement & Cursor Advancement
# ==============================================================================

@router.post("/ack", response_model=SyncAckResponse)
def acknowledge_sync_cursor_endpoint(
    payload: SyncAckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Safely acknowledge downloaded changes and advance device synchronization cursor.
    """
    device = get_verified_device(db, payload.device_id, current_user)
    advance_device_cursor(db, device, payload.acknowledged_cursor)
    return SyncAckResponse(
        device_id=device.device_identifier,
        acknowledged_cursor=device.sync_cursor,
        status="success",
        updated_at=device.updated_at,
    )


# ==============================================================================
# Synchronization Status & Conflict Management
# ==============================================================================

@router.get("/status")
def get_sync_status_endpoint(
    device_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return overall synchronization health, device status, and pending conflicts count.
    """
    device_info = None
    if device_id:
        try:
            d = get_verified_device(db, device_id, current_user)
            device_info = {
                "device_identifier": d.device_identifier,
                "is_active": d.is_active,
                "is_revoked": d.is_revoked,
                "sync_cursor": d.sync_cursor,
                "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
            }
        except Exception:
            pass

    pending_conflicts = (
        db.query(SyncConflict)
        .filter(SyncConflict.user_id == current_user.id, SyncConflict.resolution_status == "PENDING")
        .count()
    )

    return {
        "status": "online",
        "server_time": utc_now().isoformat(),
        "user_id": current_user.id,
        "device": device_info,
        "pending_conflicts": pending_conflicts,
    }


@router.get("/conflicts", response_model=List[SyncConflictResponse])
def get_conflicts_endpoint(
    device_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List synchronization conflicts requiring operational review.
    """
    q = db.query(SyncConflict)
    if current_user.role not in ["admin", "superadmin"]:
        q = q.filter(SyncConflict.user_id == current_user.id)
    if device_id:
        d = db.query(DeviceRegistration).filter(DeviceRegistration.device_identifier == device_id).first()
        if d:
            q = q.filter(SyncConflict.device_id == d.id)

    conflicts = q.order_by(SyncConflict.created_at.desc()).all()
    results = []
    for c in conflicts:
        results.append(
            SyncConflictResponse(
                id=c.id,
                conflict_token=c.conflict_token,
                action_uuid=c.action_uuid,
                device_id=c.device_id,
                user_id=c.user_id,
                mission_id=c.mission_id,
                encounter_id=c.encounter_id,
                conflict_category=c.conflict_category,
                reason=c.reason,
                client_state=json.loads(c.client_state_json) if c.client_state_json else {},
                server_state=json.loads(c.server_state_json) if c.server_state_json else {},
                resolution_status=c.resolution_status,
                resolution_notes=c.resolution_notes,
                resolved_by_user_id=c.resolved_by_user_id,
                resolved_at=c.resolved_at,
                created_at=c.created_at,
            )
        )
    return results


@router.post("/conflicts/{conflict_token}/reconcile", response_model=SyncConflictResponse)
def reconcile_conflict_endpoint(
    conflict_token: str,
    payload: SyncConflictReconcileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reconcile a synchronization conflict (RESOLVED_SERVER, RESOLVED_CLIENT, DISCARDED).
    """
    c = reconcile_sync_conflict(
        db=db,
        conflict_token=conflict_token,
        resolver_user=current_user,
        resolution=payload.resolution,
        notes=payload.notes,
    )
    return SyncConflictResponse(
        id=c.id,
        conflict_token=c.conflict_token,
        action_uuid=c.action_uuid,
        device_id=c.device_id,
        user_id=c.user_id,
        mission_id=c.mission_id,
        encounter_id=c.encounter_id,
        conflict_category=c.conflict_category,
        reason=c.reason,
        client_state=json.loads(c.client_state_json) if c.client_state_json else {},
        server_state=json.loads(c.server_state_json) if c.server_state_json else {},
        resolution_status=c.resolution_status,
        resolution_notes=c.resolution_notes,
        resolved_by_user_id=c.resolved_by_user_id,
        resolved_at=c.resolved_at,
        created_at=c.created_at,
    )


@router.post("/recovery/cycle", tags=["Internal / Worker"])
def trigger_recovery_cycle_endpoint(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Trigger manual maintenance and recovery worker cycle.
    """
    return run_sync_recovery_cycle(db)
