import os
import time
import logging
from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from app.redis_client import get_redis_client

logger = logging.getLogger("careon.rate_limiter")

# In testing mode, rate limiting is disabled to avoid cross-test state pollution.
# Set CAREON_TESTING=true in the environment or pytest fixtures to bypass limits.
_TESTING = os.getenv("CAREON_TESTING", "").lower() in ("1", "true", "yes")

# Configurable rate limit defaults (count, window_seconds)
LIMITS = {
    "auth": (
        int(os.getenv("RATE_LIMIT_AUTH_COUNT", "10")),
        int(os.getenv("RATE_LIMIT_AUTH_WINDOW", "60")),
    ),
    "otp": (
        int(os.getenv("RATE_LIMIT_OTP_COUNT", "5")),
        int(os.getenv("RATE_LIMIT_OTP_WINDOW", "60")),
    ),
    "emergency": (
        int(os.getenv("RATE_LIMIT_EMERGENCY_COUNT", "60")),
        int(os.getenv("RATE_LIMIT_EMERGENCY_WINDOW", "60")),
    ),
    "tracking": (
        int(os.getenv("RATE_LIMIT_TRACKING_COUNT", "60")),
        int(os.getenv("RATE_LIMIT_TRACKING_WINDOW", "60")),
    ),
}

TRUSTED_PROXIES = {
    ip.strip()
    for ip in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1").split(",")
    if ip.strip()
}


def get_client_ip(request: Request) -> str:
    """
    Safely extract the real client IP without trusting arbitrary forwarded headers,
    unless the immediate peer is in the trusted proxies list.
    """
    direct_ip = request.client.host if request.client else "unknown"
    if direct_ip in TRUSTED_PROXIES:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # First IP in the comma-separated list is the original client IP
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip
    return direct_ip


def rate_limit(scope: str) -> Callable:
    """
    FastAPI dependency factory enforcing rate limits using Redis.
    Fails open gracefully if Redis is unavailable to protect emergency operations.
    """
    max_requests, window_seconds = LIMITS.get(scope, (60, 60))

    async def dependency(request: Request):
        # Bypass in test mode to prevent cross-test Redis state from causing failures
        if _TESTING:
            return
        client_ip = get_client_ip(request)
        redis_client = get_redis_client()

        # If Redis is unavailable, fail open with a warning to never block emergency reporting
        if not redis_client:
            return

        key = f"rate_limit:{scope}:{client_ip}"
        try:
            # Atomic pipeline using INCR and TTL
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            current_count, current_ttl = pipe.execute()

            # Set expiration on first request
            if current_ttl is None or current_ttl < 0:
                redis_client.expire(key, window_seconds)
                current_ttl = window_seconds

            if current_count > max_requests:
                retry_after = max(current_ttl, 1)
                logger.warning(
                    f"Rate limit exceeded for {scope} from IP {client_ip}. "
                    f"Count: {current_count}/{max_requests}, Retry-After: {retry_after}s"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {scope}. Please retry in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"Error checking rate limit in Redis for {key}: {exc}. Allowing request through.")
            return

    return dependency

