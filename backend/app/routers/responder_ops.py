"""
CareOn Milestone 6 — Responder Operations & Notification Router.

Endpoints:
- Device push token registration & deactivation
- Mission acknowledgement (accept / reject)
- Mission lifecycle state transitions with client idempotency
- Immutable mission audit trail history
- High-frequency & buffered offline telemetry batch ingestion
- Responder notification history
- Acknowledgement timeout sweep
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User,
    Assignment,
    DeviceRegistration,
    NotificationDeliveryLog,
    MissionEventLog,
    utc_now,
)
from app.rbac.dependencies import get_current_user_flexible, require_role
from app.rbac.roles import UserRole
from app.schemas import (
    DeviceRegistrationCreate,
    DeviceRegistrationResponse,
    MissionAcknowledgementRequest,
    MissionTransitionRequest,
    MissionTransitionResponse,
    MissionEventLogResponse,
    TelemetryBatchRequest,
    NotificationDeliveryResponse,
)
from app.responder_ops import (
    MissionStatus,
    MissionTransitionError,
    execute_mission_transition,
    get_mission_event_history,
    check_and_process_acknowledgement_timeouts,
    notification_service,
    ingest_resource_telemetry,
    TelemetryIngestPoint,
    TelemetryValidationError,
)

logger = logging.getLogger("careon.routers.responder_ops")

router = APIRouter(prefix="/api/responder", tags=["Responder Operations"])


# ==============================================================================
# 1. Device Registration & Push Notification Endpoints
# ==============================================================================

@router.post("/devices/register", response_model=DeviceRegistrationResponse)
def register_device_token(
    payload: DeviceRegistrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Register or refresh a push notification token (FCM, APNs, or WebPush)
    associated with the authenticated responder or user.
    """
    reg = notification_service.register_device(
        db=db,
        user_id=current_user.id,
        device_token=payload.device_token,
        platform=payload.platform,
        device_model=payload.device_model,
        app_version=payload.app_version,
    )
    return reg


@router.delete("/devices/{device_token}")
def deactivate_device_token(
    device_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Deactivate a device push token upon user logout or notification revocation.
    """
    success = notification_service.deactivate_device(db=db, device_token=device_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device token not found or already inactive",
        )
    return {"status": "deactivated", "device_token": device_token}


@router.get("/notifications/history", response_model=List[NotificationDeliveryResponse])
def get_user_notification_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve logged push notification alerts dispatched to the authenticated user."""
    logs = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.user_id == current_user.id)
        .order_by(NotificationDeliveryLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs


# ==============================================================================
# 2. Mission Acknowledgement & Lifecycle Transitions
# ==============================================================================

@router.post("/missions/{assignment_id}/acknowledge", response_model=MissionTransitionResponse)
def acknowledge_mission(
    assignment_id: int,
    payload: MissionAcknowledgementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Acknowledge an assigned emergency mission:
    - 'accept': Transitions mission to ACCEPTED and initiates en-route workflow.
    - 'reject': Requires mandatory rejection_reason, releases resource to Available, and alerts dispatchers.
    """
    action = payload.action.strip().lower()
    if action not in ("accept", "reject"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be either 'accept' or 'reject'",
        )

    target_status = MissionStatus.ACCEPTED if action == "accept" else MissionStatus.REJECTED

    if target_status == MissionStatus.REJECTED and not (payload.rejection_reason and payload.rejection_reason.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mandatory rejection_reason must be provided when rejecting a mission assignment",
        )

    try:
        result = execute_mission_transition(
            db=db,
            assignment_id=assignment_id,
            target_status=target_status,
            actor=current_user,
            client_action_id=payload.client_action_id,
            rejection_reason=payload.rejection_reason,
            notes=f"Mission {action}ed by responder",
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except MissionTransitionError as mte:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(mte))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return MissionTransitionResponse(
        assignment_id=result.assignment_id,
        incident_id=result.incident_id,
        resource_id=result.resource_id,
        previous_status=result.previous_status,
        current_status=result.current_status,
        is_duplicate_replay=result.is_duplicate_replay,
        server_timestamp=result.server_timestamp,
    )


@router.post("/missions/{assignment_id}/transition", response_model=MissionTransitionResponse)
def update_mission_lifecycle(
    assignment_id: int,
    payload: MissionTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Transition a mission through its formal operational state machine:
    ASSIGNED -> ACCEPTED -> EN_ROUTE_INCIDENT -> ARRIVED_SCENE -> PATIENT_CONTACT ->
    PATIENT_PICKED_UP -> EN_ROUTE_HOSPITAL -> ARRIVED_HOSPITAL -> HANDOVER_INITIATED ->
    HANDOVER_COMPLETED -> COMPLETED (or CANCELLED).
    """
    try:
        result = execute_mission_transition(
            db=db,
            assignment_id=assignment_id,
            target_status=payload.target_status,
            actor=current_user,
            client_action_id=payload.client_action_id,
            client_timestamp=payload.client_timestamp,
            latitude=payload.latitude,
            longitude=payload.longitude,
            hospital_id=payload.hospital_id,
            notes=payload.notes,
            rejection_reason=payload.rejection_reason,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except MissionTransitionError as mte:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(mte))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))

    return MissionTransitionResponse(
        assignment_id=result.assignment_id,
        incident_id=result.incident_id,
        resource_id=result.resource_id,
        previous_status=result.previous_status,
        current_status=result.current_status,
        is_duplicate_replay=result.is_duplicate_replay,
        server_timestamp=result.server_timestamp,
    )


@router.get("/missions/{assignment_id}/history", response_model=List[MissionEventLogResponse])
def get_mission_history(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Retrieve the complete immutable mission audit trail and state timeline."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    events = get_mission_event_history(db, assignment_id)
    return events


# ==============================================================================
# 3. Telemetry & Location Ingestion
# ==============================================================================

@router.post("/telemetry/batch")
def ingest_telemetry_batch(
    payload: TelemetryBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Ingest live or buffered GPS telemetry coordinates for a responder resource.
    Supports offline sync, battery reporting, and speed anomaly validation.
    """
    ingest_points = [
        TelemetryIngestPoint(
            latitude=pt.latitude,
            longitude=pt.longitude,
            speed=pt.speed,
            heading=pt.heading,
            accuracy=pt.accuracy,
            battery_level=pt.battery_level,
            network_type=pt.network_type,
            is_buffered=pt.is_buffered,
            client_action_id=pt.client_action_id,
            client_timestamp=pt.client_timestamp,
        )
        for pt in payload.points
    ]

    try:
        result = ingest_resource_telemetry(
            db=db,
            resource_id=payload.resource_id,
            user=current_user,
            points=ingest_points,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except TelemetryValidationError as tve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(tve))

    return result


# ==============================================================================
# 4. Timeout Supervision & Sweeper
# ==============================================================================

@router.post("/assignments/sweep-timeouts")
def sweep_assignment_timeouts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Administrative and background sweep endpoint to detect and record
    unacknowledged mission timeouts. Alerts dispatchers without silently reassigning.
    """
    user_role = (current_user.role or "").lower()
    if user_role not in ("superadmin", "super_admin", "dispatcher", "admin", "org_admin", "organization_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only dispatchers and administrators can trigger timeout sweeps",
        )

    results = check_and_process_acknowledgement_timeouts(db)
    return {"processed_timeouts": len(results), "timeouts": results}
