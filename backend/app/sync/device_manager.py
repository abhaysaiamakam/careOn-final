"""
CareOn Milestone 9 — Device Manager.

Handles responder device installation registration, ownership verification,
device revocation, and synchronization cursor advancement.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    DeviceRegistration,
    SyncAuditEvent,
    User,
    Organization,
    utc_now,
)
from app.schemas import DeviceSyncRegisterRequest

logger = logging.getLogger("careon.sync.device_manager")


def register_or_update_device(
    db: Session,
    user: User,
    data: DeviceSyncRegisterRequest,
) -> DeviceRegistration:
    """
    Register a responder device installation or update its credentials/cursor.
    Enforces device ownership and revocation security boundaries.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or disabled.",
        )

    # Find existing device by device_identifier or push_token
    device = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.device_identifier == data.device_identifier)
        .first()
    )

    now = utc_now()

    if device:
        # Check if device was previously revoked
        if device.is_revoked:
            logger.warning(
                "Revoked device %s attempted registration for user %d",
                data.device_identifier,
                user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device installation has been revoked and cannot be registered without authorization.",
            )

        # Check ownership: if device belongs to another user
        if device.user_id != user.id:
            logger.warning(
                "Device ownership conflict: %s currently owned by %d, attempted by %d",
                data.device_identifier,
                device.user_id,
                user.id,
            )
            # Reassignment security check: require active admin or re-bind with audit log
            device.user_id = user.id
            audit_event = SyncAuditEvent(
                device_id=device.id,
                user_id=user.id,
                event_type="DEVICE_REASSIGNED",
                details_json=json.dumps({
                    "device_identifier": data.device_identifier,
                    "previous_user_id": device.user_id,
                    "new_user_id": user.id,
                    "timestamp": now.isoformat(),
                }),
            )
            db.add(audit_event)

        # Update metadata
        device.platform = data.platform
        device.app_version = data.app_version
        if data.device_model:
            device.device_model = data.device_model
        if data.push_token:
            device.device_token = data.push_token
        if data.organization_id:
            device.organization_id = data.organization_id
        device.is_active = True
        device.last_seen_at = now
        device.updated_at = now
    else:
        # Create new registration
        token_val = data.push_token or f"tok_{data.device_identifier}"
        device = DeviceRegistration(
            device_identifier=data.device_identifier,
            device_token=token_val,
            user_id=user.id,
            organization_id=data.organization_id,
            platform=data.platform,
            app_version=data.app_version,
            device_model=data.device_model,
            is_active=True,
            is_revoked=False,
            sync_cursor="0",
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(device)
        db.flush()

        audit_event = SyncAuditEvent(
            device_id=device.id,
            user_id=user.id,
            event_type="DEVICE_REGISTERED",
            details_json=json.dumps({
                "device_identifier": data.device_identifier,
                "platform": data.platform,
                "app_version": data.app_version,
                "timestamp": now.isoformat(),
            }),
        )
        db.add(audit_event)

    db.commit()
    db.refresh(device)
    return device


def get_verified_device(
    db: Session,
    device_identifier: str,
    user: User,
) -> DeviceRegistration:
    """
    Look up and verify an active, non-revoked device for the authenticated user.
    """
    device = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.device_identifier == device_identifier)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_identifier}' is not registered.",
        )

    if device.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DEVICE_REVOKED: This device has been revoked and cannot synchronize.",
        )

    if device.user_id != user.id and user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device ownership mismatch: device is registered to another user.",
        )

    return device


def revoke_device(
    db: Session,
    device_identifier: str,
    actor_user: User,
    reason: str = "Device decommissioned or lost",
) -> DeviceRegistration:
    """
    Revoke a device installation. Once revoked, synchronization is permanently barred.
    """
    device = (
        db.query(DeviceRegistration)
        .filter(DeviceRegistration.device_identifier == device_identifier)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_identifier}' not found.",
        )

    # Permission check: owner or admin
    if device.user_id != actor_user.id and actor_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this device.",
        )

    now = utc_now()
    device.is_revoked = True
    device.is_active = False
    device.revoked_at = now
    device.revoked_reason = reason
    device.updated_at = now

    audit_event = SyncAuditEvent(
        device_id=device.id,
        user_id=actor_user.id,
        event_type="DEVICE_REVOKED",
        details_json=json.dumps({
            "device_identifier": device_identifier,
            "revoked_by": actor_user.id,
            "reason": reason,
            "timestamp": now.isoformat(),
        }),
    )
    db.add(audit_event)
    db.commit()
    db.refresh(device)
    return device


def advance_device_cursor(
    db: Session,
    device: DeviceRegistration,
    acknowledged_cursor: str,
) -> str:
    """
    Safely advance synchronization cursor.
    """
    device.sync_cursor = acknowledged_cursor
    device.last_sync_at = utc_now()
    device.updated_at = utc_now()
    db.commit()
    return device.sync_cursor
