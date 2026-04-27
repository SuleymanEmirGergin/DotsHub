"""FastAPI lifespan — startup + shutdown hooks bound to app.state.

Two responsibilities:
    1. Connect Redis if `REDIS_URL` is set (rate-limit + idempotency
       backend). Failures degrade to the in-memory fallback rather than
       failing startup — a Redis outage shouldn't take the API offline.
    2. Initialise the local SQLAlchemy database (legacy session/result
       tables — pre-Supabase). Failure here is also non-fatal; only
       the legacy /v1/session/* routes need it.

Both clients land on app.state so middleware + routes can read them
via getattr(request.app.state, "redis", None).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.models.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.app_env = settings.APP_ENV
    redis_client = None
    if getattr(settings, "REDIS_URL", None) and "redis://" in (settings.REDIS_URL or ""):
        try:
            from redis.asyncio import Redis
            redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.ping()
            app.state.redis = redis_client
            logger.info("Redis connected for rate limiting")
        except Exception as e:
            logger.warning("Redis unavailable; using in-memory rate limit: %s", e)
            app.state.redis = None
    else:
        app.state.redis = None
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(
            "Database init failed; API will still start",
            exc_info=True,
            extra={"error": str(e)},
        )
    yield
    if redis_client:
        try:
            await redis_client.aclose()
        except Exception:
            pass
