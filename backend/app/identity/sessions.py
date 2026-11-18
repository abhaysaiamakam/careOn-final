"""
sessions.py — CareOn M2 Identity Module

HTTP session and device identification helpers.
"""

from typing import Optional
import uuid
from fastapi import Request


def get_or_create_session_id(request: Request) -> str:
    """
    Extract session ID from X-Session-ID header or query,
    or generate a fresh cryptographically random UUID4.
    """
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        session_id = request.query_params.get("session_id")
    if not session_id or len(session_id.strip()) == 0:
        session_id = str(uuid.uuid4())
    return session_id.strip()[:64]


def extract_device_hint(request: Request) -> str:
    """
    Extract a sanitized, truncated user-agent string to serve as a device hint.
    """
    ua = request.headers.get("User-Agent", "Unknown Device")
    return ua.strip()[:200]
