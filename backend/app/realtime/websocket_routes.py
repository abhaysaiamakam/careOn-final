"""
CareOn Milestone 4 — WebSocket and Real-Time Coordination Routes.

Provides:
- WebSocket endpoint (/ws and /api/ws) with JWT authentication and subscription management.
- Live GPS telemetry ingestion endpoint (/api/realtime/telemetry).
- Real-time subsystem health indicator (/api/realtime/health).
- Historical event replay endpoint for client recovery (/api/realtime/history).
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Resource,
    Assignment,
    Incident,
    OutboxEvent,
    make_point_wkt,
    utc_now,
)
from app.redis_client import get_redis_client
from app.rbac.dependencies import get_current_user_flexible, require_role
from app.rbac.roles import UserRole
from app.realtime.authorization import (
    authenticate_ws_token,
    can_subscribe_channel,
    RealtimeUserSession,
)
from app.realtime.connection_manager import connection_manager
from app.realtime.event_models import (
    EventTypes,
    get_global_channel,
    get_org_channel,
    get_incident_channel,
    get_responder_channel,
    get_gps_cache_key,
)
from app.realtime.event_publisher import record_and_publish_event, get_event_history
from app.realtime.redis_subscriber import redis_subscriber

logger = logging.getLogger("careon.realtime.routes")

router = APIRouter(tags=["Real-Time Coordination"])


# ==============================================================================
# WebSocket Endpoint (/ws and /api/ws)
# ==============================================================================
async def handle_websocket_connection(websocket: WebSocket, token: Optional[str] = None, db: Optional[Session] = None):
    """Core WebSocket handler supporting both query token and initial auth frame."""
    await websocket.accept()

    should_close_db = False
    if db is None:
        from app.database import get_db
        db = next(get_db())
        should_close_db = True
    session: Optional[RealtimeUserSession] = None

    try:
        # 1. Attempt token authentication from query param
        if token:
            session = authenticate_ws_token(token, db)
            if not session:
                logger.warning("Rejecting unauthorized WebSocket connection (invalid query token).")
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "type": "error",
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Valid M2 Bearer JWT access token required.",
                }))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        else:
            # 2. If no query token, prompt client and wait up to 10 seconds for initial auth frame
            await websocket.send_text(json.dumps({
                "event": "auth_required",
                "type": "auth_required",
                "message": "Please send {'action': 'auth', 'token': '<jwt>'} within 10 seconds.",
            }))
            try:
                raw_frame = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                data = json.loads(raw_frame)
                if (data.get("action") == "auth" or data.get("type") == "auth") and data.get("token"):
                    session = authenticate_ws_token(data["token"], db)
            except (asyncio.TimeoutError, json.JSONDecodeError):
                pass

            if not session:
                logger.warning("Rejecting unauthorized WebSocket connection attempt.")
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "type": "error",
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Valid M2 Bearer JWT access token required.",
                }))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        # 4. Register connection
        conn = await connection_manager.connect(websocket, session)

        # 5. Automatically subscribe to authorized default channels
        default_channels = []
        if session.is_dispatcher or session.is_super_admin:
            await connection_manager.subscribe(conn.connection_id, get_global_channel())
            default_channels.append(get_global_channel())

        for org_id in session.org_ids:
            org_chan = get_org_channel(org_id)
            await connection_manager.subscribe(conn.connection_id, org_chan)
            default_channels.append(org_chan)

        if session.is_responder:
            resp_chan = get_responder_channel(session.user_id)
            await connection_manager.subscribe(conn.connection_id, resp_chan)
            default_channels.append(resp_chan)

        # Send welcome / authenticated envelope
        await websocket.send_text(json.dumps({
            "event": "authenticated" if not token else "connected",
            "type": "connected",
            "connection_id": conn.connection_id,
            "user_id": session.user_id,
            "role": session.role.value,
            "user": {
                "id": session.user_id,
                "email": session.email,
                "role": session.role.value,
            },
            "subscriptions": default_channels,
            "timestamp": utc_now().isoformat(),
        }))

        # 6. Main client message processing loop
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"event": "error", "type": "error", "message": "Invalid JSON frame."}))
                continue

            action = msg.get("action")

            # Ping-Pong heartbeat
            if action == "ping":
                await websocket.send_text(json.dumps({
                    "event": "pong",
                    "type": "pong",
                    "timestamp": utc_now().isoformat(),
                }))

            # Channel Subscription
            elif action == "subscribe":
                channels_to_sub = msg.get("channels") or msg.get("channel") or []
                if isinstance(channels_to_sub, str):
                    channels_to_sub = [channels_to_sub]

                sub_results = {}
                for ch in channels_to_sub:
                    if can_subscribe_channel(session, ch, db):
                        await connection_manager.subscribe(conn.connection_id, ch)
                        sub_results[ch] = "subscribed"
                    else:
                        sub_results[ch] = "denied"
                        logger.warning(
                            f"Subscription denied: user {session.email} ({session.role}) "
                            f"attempted to subscribe to unauthorized channel {ch}"
                        )

                single_ch = msg.get("channel")
                if single_ch and len(channels_to_sub) == 1:
                    status_outcome = sub_results.get(single_ch, "denied")
                    await websocket.send_text(json.dumps({
                        "event": "subscribed" if status_outcome == "subscribed" else "subscription_error",
                        "type": "subscription_result",
                        "channel": single_ch,
                        "status": status_outcome,
                        "results": sub_results,
                        "active_subscriptions": list(conn.subscriptions),
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "event": "subscription_result",
                        "type": "subscription_result",
                        "results": sub_results,
                        "active_subscriptions": list(conn.subscriptions),
                    }))

            # Channel Unsubscription
            elif action == "unsubscribe":
                channels_to_unsub = msg.get("channels") or msg.get("channel") or []
                if isinstance(channels_to_unsub, str):
                    channels_to_unsub = [channels_to_unsub]

                for ch in channels_to_unsub:
                    await connection_manager.unsubscribe(conn.connection_id, ch)

                single_unsub = msg.get("channel")
                await websocket.send_text(json.dumps({
                    "event": "unsubscribed",
                    "type": "unsubscribe_result",
                    "channel": single_unsub or (channels_to_unsub[0] if channels_to_unsub else None),
                    "unsubscribed": channels_to_unsub,
                    "active_subscriptions": list(conn.subscriptions),
                }))

            # Event Recovery / Replay
            elif action == "replay":
                since_id = msg.get("since_event_id")
                incident_id = msg.get("incident_id")
                history = get_event_history(
                    db,
                    session,
                    since_event_id=since_id,
                    incident_id=incident_id,
                    limit=msg.get("limit", 50),
                )
                await websocket.send_text(json.dumps({
                    "type": "replay_batch",
                    "events": history,
                    "count": len(history),
                }))

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown action '{action}'. Supported: ping, subscribe, unsubscribe, replay.",
                }))

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected normally: {session.email if session else 'unauthenticated'}")
    except Exception as exc:
        logger.warning(f"WebSocket connection error: {exc}")
    finally:
        if 'conn' in locals() and conn:
            await connection_manager.disconnect(conn.connection_id)
        if should_close_db and db:
            db.close()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Standard CareOn WebSocket endpoint."""
    await handle_websocket_connection(websocket, token, db)


@router.websocket("/api/ws")
async def websocket_api_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Alias WebSocket endpoint for reverse proxies and ingress controllers."""
    await handle_websocket_connection(websocket, token, db)


# ==============================================================================
# REST Real-time Telemetry Ingestion (/api/realtime/telemetry)
# ==============================================================================
@router.post("/api/realtime/telemetry")
def ingest_live_telemetry(
    payload: Dict[str, Any],
    user = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Ingest live GPS telemetry coordinates from field responders or vehicles.
    Validates coordinate bounds, caches the latest position in Redis for sub-millisecond
    lookup, persists PostGIS point geometry, and publishes a location update event.
    """
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    speed = payload.get("speed")
    heading = payload.get("heading")
    resource_id = payload.get("resource_id")

    # 1. Coordinate boundary validation
    if latitude is None or longitude is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coordinates latitude and longitude are required.")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coordinates must be valid floating point numbers.")

    if not (-90.0 <= lat <= 90.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid latitude {lat}. Must be between -90.0 and 90.0.")
    if not (-180.0 <= lon <= 180.0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid longitude {lon}. Must be between -180.0 and 180.0.")

    # 2. Check impossible jump / speed (e.g. speed > 350 km/h)
    if speed is not None:
        try:
            spd = float(speed)
            if spd > 350.0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid velocity: telemetry speed exceeds operational limits.")
        except ValueError:
            pass

    # 3. Resolve resource
    resource = None
    if resource_id:
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
    else:
        resource = db.query(Resource).filter(Resource.assigned_user_id == user.id).first()

    if not resource:
        # Fallback for dispatcher/admin test coordinates
        resource = db.query(Resource).first()
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching resource found for telemetry update.")

    # 4. Check ownership / permission
    role_str = getattr(user, "role", "").lower()
    if role_str in ("citizen", "user", "guest"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized: citizens cannot transmit field telemetry.")

    is_admin = role_str in ("admin", "super_admin", "dispatcher")
    if not is_admin and resource.assigned_user_id and resource.assigned_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized: cannot update telemetry for another unit.")

    # 5. Update PostGIS geometry & timestamp
    resource.latitude = lat
    resource.longitude = lon
    resource.geom = make_point_wkt(lat, lon)
    resource.last_updated = utc_now()
    db.commit()

    # 6. Cache high-frequency latest coordinate in Redis
    telemetry_data = {
        "resource_id": resource.id,
        "resource_code": resource.resource_code,
        "resource_name": resource.name,
        "latitude": lat,
        "longitude": lon,
        "speed": speed,
        "heading": heading,
        "status": resource.status,
        "timestamp": resource.last_updated.isoformat(),
    }
    try:
        r = get_redis_client()
        if r:
            r.set(get_gps_cache_key(resource.id), json.dumps(telemetry_data), ex=120)
    except Exception as exc:
        logger.warning(f"Redis GPS cache write failed: {exc}")

    # 7. Publish location updated event to global and responder channels
    record_and_publish_event(
        db=db,
        event_type=EventTypes.RESPONDER_LOCATION_UPDATED,
        payload=telemetry_data,
        actor_id=user.id,
        channel=get_global_channel(),
    )

    return {
        "status": "success",
        "resource_id": resource.id,
        "resource_code": resource.resource_code,
        "latitude": lat,
        "longitude": lon,
        "speed": speed,
        "timestamp": resource.last_updated.isoformat(),
    }


# ==============================================================================
# Real-Time Engine Health & Metrics (/api/realtime/health)
# ==============================================================================
@router.get("/api/realtime/health")
def get_realtime_health(db: Session = Depends(get_db)):
    """Operational health and metrics of the real-time coordination engine."""
    conn_metrics = connection_manager.get_metrics()

    # Check Redis Pub/Sub connectivity
    r = get_redis_client()
    redis_pubsub_connected = redis_subscriber.is_connected or bool(r and r.ping())

    # Count outbox pending backlog
    unpub_count = (
        db.query(func.count(OutboxEvent.id))
        .filter(OutboxEvent.is_published == False)
        .scalar()
        or 0
    )

    return {
        "status": "healthy" if redis_pubsub_connected else "degraded",
        "redis_pubsub": "connected" if redis_pubsub_connected else "disconnected",
        "redis_pubsub_connected": redis_pubsub_connected,
        "websocket_connections": conn_metrics["active_connections"],
        "active_websockets": conn_metrics["active_connections"],
        "subscribed_channels": conn_metrics["subscribed_channels"],
        "total_messages_sent": conn_metrics["total_messages_sent"],
        "total_messages_dropped": conn_metrics["total_messages_dropped"],
        "outbox_backlog": unpub_count,
        "outbox_backlog_count": unpub_count,
        "timestamp": utc_now().isoformat(),
    }


# ==============================================================================
# Historical Event Replay (/api/realtime/history)
# ==============================================================================
@router.get("/api/realtime/history")
def query_event_history(
    since_event_id: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    incident_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Cursor-based event history recovery for reconnecting clients."""
    from app.realtime.authorization import RealtimeUserSession, _resolve_user_role
    role = _resolve_user_role(user)
    session = RealtimeUserSession(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=role,
    )
    events = get_event_history(
        db=db,
        session=session,
        since_event_id=since_event_id,
        channel=channel,
        incident_id=incident_id,
        limit=limit,
    )
    return {
        "count": len(events),
        "channel": channel,
        "since_event_id": since_event_id,
        "events": events,
    }
