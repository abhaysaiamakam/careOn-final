"""
CareOn Milestone 4 — Redis Pub/Sub Background Subscriber.

Connects to Redis using redis.asyncio, subscribes to the channel pattern `careon:events:*`,
and distributes incoming events across locally connected WebSockets.
Supports multiple FastAPI process instances: an event published by Node A is received
and broadcast to clients connected to Node B.
"""

import asyncio
import json
import logging
import os
from typing import Optional
import redis.asyncio as aioredis

from app.realtime.connection_manager import connection_manager

logger = logging.getLogger("careon.realtime.subscriber")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class RedisEventSubscriber:
    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[aioredis.Redis] = None
        self.is_connected = False
        self.total_events_received = 0

    def start(self):
        """Start the subscriber background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Started Redis Pub/Sub event listener task")

    async def stop(self):
        """Gracefully stop subscriber task and close connection."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._client:
            try:
                if hasattr(self._client, "aclose"):
                    await self._client.aclose()
                else:
                    await self._client.close()
            except Exception:
                pass
            self._client = None
        self.is_connected = False
        logger.info("Stopped Redis Pub/Sub event listener")

    async def _listen_loop(self):
        """Main listening loop with automatic reconnection on network drops."""
        backoff = 1.0
        while self._running:
            try:
                logger.info(f"Connecting to Redis Pub/Sub at {self.redis_url}...")
                self._client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3.0,
                )
                pubsub = self._client.pubsub()
                await pubsub.psubscribe("careon:events:*")
                self.is_connected = True
                backoff = 1.0
                logger.info("Successfully subscribed to Redis channels 'careon:events:*'")

                async for message in pubsub.listen():
                    if not self._running:
                        break

                    msg_type = message.get("type")
                    if msg_type in ("pmessage", "message"):
                        channel = message.get("channel")
                        data_str = message.get("data")
                        if channel and data_str:
                            try:
                                event_dict = json.loads(data_str)
                                self.total_events_received += 1
                                await connection_manager.broadcast_to_channel(channel, event_dict)
                            except Exception as exc:
                                logger.warning(f"Error handling Redis event on {channel}: {exc}")

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.is_connected = False
                logger.warning(
                    f"Redis Pub/Sub connection dropped ({exc}). Reconnecting in {backoff:.1f}s..."
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)


# Global subscriber singleton
redis_subscriber = RedisEventSubscriber()
