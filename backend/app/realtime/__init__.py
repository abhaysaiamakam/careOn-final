"""
CareOn Real-Time Coordination Engine Package.
"""

from app.realtime.event_models import RealtimeEvent, EventTypes
from app.realtime.event_publisher import record_and_publish_event, relay_pending_outbox_events
from app.realtime.connection_manager import connection_manager
from app.realtime.redis_subscriber import redis_subscriber
from app.realtime.websocket_routes import router as realtime_router

__all__ = [
    "RealtimeEvent",
    "EventTypes",
    "record_and_publish_event",
    "relay_pending_outbox_events",
    "connection_manager",
    "redis_subscriber",
    "realtime_router",
]
