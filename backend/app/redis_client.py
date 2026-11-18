import os
import logging
from typing import Optional
import redis

logger = logging.getLogger("careon.redis")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get or create a reusable Redis client connection pool.
    Gracefully returns None if Redis is unreachable.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
        client.ping()
        _redis_client = client
        logger.info(f"Connected to Redis at {REDIS_URL}")
        return _redis_client
    except Exception as exc:
        logger.warning(f"Redis is unavailable at {REDIS_URL}: {exc}. Operating in fallback mode.")
        return None


def is_redis_available() -> bool:
    """Check whether Redis is currently responsive."""
    try:
        client = get_redis_client()
        return bool(client and client.ping())
    except Exception:
        return False


def reset_redis_client_for_tests():
    """Reset singleton for isolated tests."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None

