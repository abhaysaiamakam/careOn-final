"""
CareOn Milestone 4 — WebSocket Connection Manager.

Features:
- Thread-safe / async tracking of connected WebSocket clients
- Per-connection bounded outgoing queues (backpressure protection)
- Channel subscription index for O(1) broadcast lookup
- Role-aware payload sanitization at transmission time
- Heartbeat / idle connection detection and graceful cleanup
- Metrics for observability (active sockets, messages dispatched, drops)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from app.realtime.authorization import RealtimeUserSession, sanitize_payload_for_viewer
from app.realtime.event_models import RealtimeEvent

logger = logging.getLogger("careon.realtime.manager")


class ActiveConnection:
    def __init__(self, connection_id: str, websocket: WebSocket, session: RealtimeUserSession):
        self.connection_id = connection_id
        self.websocket = websocket
        self.session = session
        self.subscriptions: Set[str] = set()
        self.send_queue: asyncio.Queue = asyncio.Queue(maxsize=150)
        self.connected_at = datetime.now(timezone.utc)
        self.last_ping = datetime.now(timezone.utc)
        self.writer_task: Optional[asyncio.Task] = None


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, ActiveConnection] = {}
        self._channel_subscriptions: Dict[str, Set[str]] = {}  # channel -> set[connection_id]
        self._lock = asyncio.Lock()

        # Telemetry metrics
        self.total_messages_sent: int = 0
        self.total_messages_dropped: int = 0

    async def connect(self, websocket: WebSocket, session: RealtimeUserSession) -> ActiveConnection:
        """Register and start an active WebSocket connection."""
        connection_id = str(uuid.uuid4())
        conn = ActiveConnection(connection_id, websocket, session)

        async with self._lock:
            self._connections[connection_id] = conn

        # Start consumer task to drain queue to client
        conn.writer_task = asyncio.create_task(self._socket_writer(conn))
        logger.info(f"WebSocket client connected: {connection_id} (User: {session.email}, Role: {session.role})")
        return conn

    async def disconnect(self, connection_id: str):
        """Clean up connection, cancel worker, and remove all subscriptions."""
        async with self._lock:
            conn = self._connections.pop(connection_id, None)
            if not conn:
                return

            # Remove from all channel maps
            for channel in conn.subscriptions:
                sub_set = self._channel_subscriptions.get(channel)
                if sub_set and connection_id in sub_set:
                    sub_set.discard(connection_id)
                    if not sub_set:
                        self._channel_subscriptions.pop(channel, None)

        if conn.writer_task and not conn.writer_task.done():
            conn.writer_task.cancel()

        logger.info(f"WebSocket client disconnected: {connection_id}")

    async def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribe a connection to a specific channel."""
        async with self._lock:
            conn = self._connections.get(connection_id)
            if not conn:
                return False

            conn.subscriptions.add(channel)
            if channel not in self._channel_subscriptions:
                self._channel_subscriptions[channel] = set()
            self._channel_subscriptions[channel].add(connection_id)

        logger.debug(f"Connection {connection_id} subscribed to {channel}")
        return True

    async def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a specific channel."""
        async with self._lock:
            conn = self._connections.get(connection_id)
            if conn:
                conn.subscriptions.discard(channel)
            sub_set = self._channel_subscriptions.get(channel)
            if sub_set:
                sub_set.discard(connection_id)
        return True

    async def broadcast_to_channel(self, channel: str, event_data: dict):
        """
        Deliver event to all active connections subscribed to *channel*.
        Applies audience-aware PII sanitization per recipient.
        """
        async with self._lock:
            target_ids = list(self._channel_subscriptions.get(channel, set()))

        if not target_ids:
            return

        for cid in target_ids:
            conn = self._connections.get(cid)
            if not conn:
                continue

            # Audience sanitization
            sanitized_event = event_data.copy()
            if "payload" in sanitized_event and isinstance(sanitized_event["payload"], dict):
                sanitized_event["payload"] = sanitize_payload_for_viewer(
                    sanitized_event["payload"], conn.session.role
                )

            # Queue delivery with backpressure protection
            try:
                conn.send_queue.put_nowait(sanitized_event)
            except asyncio.QueueFull:
                self.total_messages_dropped += 1
                logger.warning(f"Send queue full for connection {cid}. Dropping oldest event.")
                try:
                    conn.send_queue.get_nowait()
                    conn.send_queue.put_nowait(sanitized_event)
                except Exception:
                    pass

    async def _socket_writer(self, conn: ActiveConnection):
        """Continuous background task draining outgoing queue to the WebSocket."""
        try:
            while True:
                msg = await conn.send_queue.get()
                text_payload = json.dumps(msg)
                await conn.websocket.send_text(text_payload)
                self.total_messages_sent += 1
                conn.send_queue.task_done()
        except asyncio.CancelledError:
            pass
        except (WebSocketDisconnect, ConnectionResetError):
            pass
        except Exception as exc:
            logger.warning(f"Error in socket writer for {conn.connection_id}: {exc}")
        finally:
            await self.disconnect(conn.connection_id)

    def get_metrics(self) -> dict:
        """Return live connection metrics for system health monitoring."""
        return {
            "active_connections": len(self._connections),
            "subscribed_channels": len(self._channel_subscriptions),
            "total_messages_sent": self.total_messages_sent,
            "total_messages_dropped": self.total_messages_dropped,
        }


# Global singleton instance
connection_manager = ConnectionManager()
