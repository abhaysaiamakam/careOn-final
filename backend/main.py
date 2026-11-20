"""Vercel entrypoint for the CareOn FastAPI application.

Configure the Vercel backend project's Root Directory as ``backend``. Keeping
this module at that root makes the FastAPI ``app`` discoverable by Vercel's
Python runtime while preserving ``app.main:app`` for local Uvicorn deployments.
"""

from app.main import app

__all__ = ["app"]
