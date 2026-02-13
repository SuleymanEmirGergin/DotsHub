"""FastAPI application entry point — V4 with unified /v1/triage/turn."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.request_id import generate_request_id, set_request_id
from app.models.database import init_db

setup_logging()
logger = logging.getLogger(__name__)
from app.api.routes.session import router as session_router
from app.api.routes.message import router as message_router
from app.api.routes.triage import router as triage_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.facilities import router as facilities_router
from app.admin_api import router as admin_router
from app.admin_v5 import router as admin_v5_router
from app.rate_limit import (
    check_rate_limit,
    check_rate_limit_redis,
    build_rl_key,
    build_admin_rl_key,
    check_admin_rate_limit,
    check_admin_rate_limit_redis,
    MAX_REQ,
    ADMIN_MAX_REQ,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
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
        logger.warning("Database init failed; API will still start", exc_info=True, extra={"error": str(e)})
    yield
    if redis_client:
        try:
            await redis_client.aclose()
        except Exception:
            pass


app = FastAPI(
    title="Dotshub - Ön-Triyaj Asistanı API",
    description="Agentic AI tabanlı akıllı ön-triyaj sistemi (V4 — unified triage turn)",
    version="4.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    """Generate request_id, set in context, add X-Request-ID to response."""
    rid = request.headers.get("X-Request-ID") or generate_request_id()
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Apply rate limit to triage turn and feedback; add X-RateLimit-* headers."""
    path = request.scope.get("path", "")
    if path not in ("/v1/triage/turn", "/v1/triage/feedback"):
        return await call_next(request)

    ip = request.client.host if request.client else None
    device_id = request.headers.get("x-device-id")
    key = build_rl_key(ip, device_id)
    redis = getattr(request.app.state, "redis", None)
    if redis:
        allowed, remaining, reset_in = await check_rate_limit_redis(redis, key)
    else:
        allowed, remaining, reset_in = check_rate_limit(key)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "reset_in_sec": reset_in},
            headers={
                "X-RateLimit-Limit": str(MAX_REQ),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_in),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(MAX_REQ)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_in)
    return response


@app.middleware("http")
async def admin_rate_limit_middleware(request, call_next):
    """Stricter rate limit for /v1/admin/* (per IP)."""
    path = request.scope.get("path", "")
    if not path.startswith("/v1/admin"):
        return await call_next(request)
    ip = request.client.host if request.client else None
    key = build_admin_rl_key(ip)
    redis = getattr(request.app.state, "redis", None)
    if redis:
        allowed, remaining, reset_in = await check_admin_rate_limit_redis(redis, key)
    else:
        allowed, remaining, reset_in = check_admin_rate_limit(key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Admin API rate limit exceeded", "reset_in_sec": reset_in},
            headers={
                "X-RateLimit-Limit": str(ADMIN_MAX_REQ),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_in),
            },
        )
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(ADMIN_MAX_REQ)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_in)
    return response


# Routes — /v1/ prefix
app.include_router(triage_router, prefix="/v1", tags=["Triage"])
app.include_router(feedback_router, prefix="/v1", tags=["Feedback"])
app.include_router(facilities_router, prefix="/v1", tags=["Facilities"])
app.include_router(session_router, prefix="/v1", tags=["Session (legacy)"])
app.include_router(message_router, prefix="/v1", tags=["Message (legacy)"])
app.include_router(admin_router, prefix="/v1", tags=["Admin"])
app.include_router(admin_v5_router, tags=["Admin V5"])


@app.get("/health")
async def health_check():
    """Basic liveness; includes Supabase reachability when configured."""
    out = {"status": "ok", "service": "dotshub-api", "version": "4.0.0"}
    if settings.SUPABASE_URL and "xxxx" not in settings.SUPABASE_URL:
        try:
            import httpx
            r = httpx.get(
                f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/",
                headers={"apikey": settings.SUPABASE_SERVICE_ROLE_KEY or ""},
                timeout=2.0,
            )
            out["supabase"] = "ok" if r.status_code in (200, 401) else f"status_{r.status_code}"
        except Exception as e:
            out["supabase"] = "error"
            out["supabase_error"] = str(e)[:200]
    else:
        out["supabase"] = "not_configured"
    return out
