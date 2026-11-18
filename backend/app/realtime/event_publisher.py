"""
CareOn Milestone 4 — Transactional Event Publisher and Outbox Engine.

Ensures:
1. Transactional Outbox guarantee: Business operations and events are persisted together.
2. At-least-once Redis Pub/Sub distribution.
3. Fail-safe isolation: Redis outages never prevent incident reporting or DB commits.
4. Outbox relay worker for retrying failed deliveries.
5. Replay recovery for reconnecting WebSocket clients.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import OutboxEvent, utc_now
from app.redis_client import get_redis_client
from app.realtime.event_models import (
    RealtimeEvent,
    get_global_channel,
    get_org_channel,
    get_incident_channel,
)
from app.realtime.connection_manager import connection_manager
from app.realtime.authorization import RealtimeUserSession, can_subscribe_channel, sanitize_payload_for_viewer

logger = logging.getLogger("careon.realtime.publisher")


def record_and_publish_event(
    db: Session,
    event_type: str,
    payload: Dict[str, Any],
    organization_id: Optional[int] = None,
    incident_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    channel: Optional[str] = None,
) -> RealtimeEvent:
    """
    Persist an event to the transactional outbox and publish to Redis Pub/Sub.
    
    If Redis is down or unavailable, the event remains in PostgreSQL with
    is_published=False, ensuring business operations are NEVER blocked or rolled back.
    """
    # 1. Resolve target channel
    if not channel:
        if incident_id:
            channel = get_incident_channel(incident_id)
        elif organization_id:
            channel = get_org_channel(organization_id)
        else:
            channel = get_global_channel()

    # 2. Build canonical event envelope
    event = RealtimeEvent(
        event_type=event_type,
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=actor_id,
        channel=channel,
        payload=payload,
    )

    # 3. Attempt Redis publication
    broadcast_data = event.to_broadcast_dict()
    is_published = False
    published_at = None
    retry_count = 0
    last_error = None
    try:
        r = get_redis_client()
        if r:
            serialized = json.dumps(broadcast_data)
            # Publish to specific channel
            r.publish(channel, serialized)
            # If channel is not global, also mirror critical incident lifecycle to global channel
            if channel != get_global_channel() and event_type.startswith("incident."):
                r.publish(get_global_channel(), serialized)

            is_published = True
            published_at = utc_now()
            logger.debug(f"Published event {event.event_id} ({event_type}) to Redis channel {channel}")
    except Exception as exc:
        retry_count = 1
        last_error = str(exc)
        logger.warning(
            f"Redis publication failed for event {event.event_id} ({exc}). "
            f"Event remains safely stored in outbox for background relay."
        )

    # 4. Save to transactional Outbox table
    outbox_record = OutboxEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        event_version=event.event_version,
        occurred_at=event.occurred_at,
        organization_id=organization_id,
        incident_id=incident_id,
        actor_id=actor_id,
        channel=channel,
        payload_json=json.dumps(payload),
        is_published=is_published,
        published_at=published_at,
        retry_count=retry_count,
        last_error=last_error,
    )
    db.add(outbox_record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    # 5. Local instance notification (delivers immediately to locally connected WebSockets)
    try:
        import asyncio
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            asyncio.create_task(connection_manager.broadcast_to_channel(channel, broadcast_data))
            if channel != get_global_channel() and event_type.startswith("incident."):
                asyncio.create_task(connection_manager.broadcast_to_channel(get_global_channel(), broadcast_data))
    except Exception as exc:
        logger.debug(f"Direct local dispatch deferred: {exc}")

    return event


def relay_pending_outbox_events(db: Session, limit: int = 50) -> int:
    """
    Background relay worker: queries pending outbox records and republishes them to Redis.
    Called periodically or after reconnects.
    """
    pending = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.is_published == False, OutboxEvent.retry_count < 10)
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )

    if not pending:
        return 0

    r = get_redis_client()
    if not r:
        return 0

    success_count = 0
    for record in pending:
        try:
            try:
                payload = json.loads(record.payload_json)
            except Exception:
                payload = {}

            event_dict = {
                "event_id": record.event_id,
                "event_type": record.event_type,
                "event_version": record.event_version,
                "occurred_at": record.occurred_at.isoformat(),
                "organization_id": record.organization_id,
                "incident_id": record.incident_id,
                "actor_id": record.actor_id,
                "channel": record.channel,
                "payload": payload,
            }
            r.publish(record.channel, json.dumps(event_dict))
            record.is_published = True
            record.published_at = utc_now()
            success_count += 1
        except Exception as exc:
            record.retry_count += 1
            record.last_error = str(exc)

    db.commit()
    return success_count


def get_event_history(
    db: Session,
    session: RealtimeUserSession,
    since_event_id: Optional[str] = None,
    channel: Optional[str] = None,
    incident_id: Optional[int] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Retrieve historical events for client reconnection recovery.
    Enforces authorization: clients only recover events for authorized channels.
    """
    query = db.query(OutboxEvent)

    if channel:
        if not can_subscribe_channel(session, channel, db):
            return []
        query = query.filter(OutboxEvent.channel == channel)
    elif incident_id:
        inc_chan = get_incident_channel(incident_id)
        if not can_subscribe_channel(session, inc_chan, db):
            return []
        query = query.filter(OutboxEvent.incident_id == incident_id)
    else:
        # Default: if dispatcher/admin, global events; if citizen, own incidents
        if session.is_dispatcher or session.is_super_admin:
            query = query.filter(OutboxEvent.channel == get_global_channel())
        else:
            return []

    if since_event_id:
        anchor = db.query(OutboxEvent.id).filter(OutboxEvent.event_id == since_event_id).first()
        if anchor:
            query = query.filter(OutboxEvent.id > anchor[0])

    records = query.order_by(OutboxEvent.id.asc()).limit(limit).all()

    results = []
    for r in records:
        try:
            payload = json.loads(r.payload_json)
        except Exception:
            payload = {}

        sanitized = sanitize_payload_for_viewer(payload, session.role)
        results.append({
            "event_id": r.event_id,
            "event_type": r.event_type,
            "event_version": r.event_version,
            "occurred_at": r.occurred_at.isoformat(),
            "organization_id": r.organization_id,
            "incident_id": r.incident_id,
            "actor_id": r.actor_id,
            "channel": r.channel,
            "payload": sanitized,
        })

    return results
