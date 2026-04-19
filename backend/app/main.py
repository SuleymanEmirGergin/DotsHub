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
from app.api.routes.summary_email import router as summary_email_router
from app.api.routes.push_token import router as push_token_router
from app.admin_api import router as admin_router
from app.admin_tenants_api import router as admin_tenants_router
from app.admin_feedback_api import router as admin_feedback_router
from app.api.routes.data_rights import router as data_rights_router
from app.admin_v5 import router as admin_v5_router
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.version_gating import CapabilityGateMiddleware
from app.rate_limit import (
    check_rate_limit,
    check_rate_limit_redis,
    build_rl_key,
    build_send_summary_rl_key,
    check_send_summary_rate_limit,
    check_send_summary_rate_limit_redis,
    build_admin_rl_key,
    check_admin_rate_limit,
    check_admin_rate_limit_redis,
    MAX_REQ,
    SEND_SUMMARY_MAX_REQ,
    ADMIN_MAX_REQ,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
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
app.add_middleware(SecurityHeadersMiddleware)
# Client-capability gating — strips payload fields for clients that did
# not advertise support for them. See app/version_gating.py for the
# protocol and docs/client_versioning.md for the rationale.
app.add_middleware(CapabilityGateMiddleware)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    """Generate request_id, set in context, add X-Request-ID to response."""
    rid = request.headers.get("X-Request-ID") or generate_request_id()
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# ── HTTP 5xx health monitor ────────────────────────────────────────────
# Rolling-window 5xx-rate watcher; paging sibling for the dashboard's
# envelope-distribution card. Wakes the Slack/Discord dispatcher when
# the last HTTP_5XX_ALERT_WINDOW requests have success rate below
# HTTP_5XX_ALERT_SUCCESS_THRESHOLD_PCT and the cool-down allows it.
# In-memory per worker, same pattern / trade-offs as the LLM health
# monitor in services/llm_nlu.py.
from collections import Counter as _Counter, deque as _deque
from threading import Lock as _Lock
import time as _time

_HTTP_LOCK = _Lock()
_HTTP_EVENTS: _deque = _deque()  # (is_5xx: bool, status_code: int, path: str)
_HTTP_LAST_ALERT_TS: float = 0.0


def _http_observe(status: int, path: str) -> None:
    if not getattr(settings, "HTTP_5XX_ALERT_ENABLED", True):
        return
    window = int(getattr(settings, "HTTP_5XX_ALERT_WINDOW", 50))
    min_reqs = int(getattr(settings, "HTTP_5XX_ALERT_MIN_REQS", 20))
    threshold = float(getattr(settings, "HTTP_5XX_ALERT_SUCCESS_THRESHOLD_PCT", 95.0))
    cooldown = float(getattr(settings, "HTTP_5XX_ALERT_COOLDOWN_SEC", 600))

    is_5xx = status >= 500
    global _HTTP_LAST_ALERT_TS
    with _HTTP_LOCK:
        _HTTP_EVENTS.append((is_5xx, status, path))
        while len(_HTTP_EVENTS) > window:
            _HTTP_EVENTS.popleft()
        n = len(_HTTP_EVENTS)
        if n < min_reqs:
            return
        fails = sum(1 for b, _s, _p in _HTTP_EVENTS if b)
        success_pct = 100.0 * (n - fails) / n
        if success_pct >= threshold:
            return
        now = _time.monotonic()
        if now - _HTTP_LAST_ALERT_TS < cooldown:
            return
        _HTTP_LAST_ALERT_TS = now
        # Find the most-hit 5xx (path, status) pair for the alert body.
        pairs = _Counter((p, s) for b, s, p in _HTTP_EVENTS if b)
        top_pair = pairs.most_common(1)[0][0] if pairs else (None, None)
        top_path, top_status = top_pair

    try:
        from app.notifier import send_http_5xx_alert

        send_http_5xx_alert(
            success_rate_pct=success_pct,
            window_size=n,
            top_path=top_path,
            top_status=top_status,
            threshold_pct=threshold,
        )
    except Exception:
        pass


@app.middleware("http")
async def http_5xx_monitor_middleware(request, call_next):
    """Observe every response; surface 5xx rate spikes as webhook alerts."""
    try:
        response = await call_next(request)
        _http_observe(response.status_code, request.scope.get("path", "?"))
        return response
    except Exception:
        # Unhandled exception → treat as 500 for observability, then
        # let FastAPI's default handler produce the actual response.
        _http_observe(500, request.scope.get("path", "?"))
        raise


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Apply rate limit to triage turn, feedback, send-summary, and export-summary; add X-RateLimit-* headers."""
    path = request.scope.get("path", "")
    ip = request.client.host if request.client else None

    if path in ("/v1/triage/send-summary", "/v1/triage/export-summary"):
        key = build_send_summary_rl_key(ip)
        redis = getattr(request.app.state, "redis", None)
        if redis:
            allowed, remaining, reset_in = await check_send_summary_rate_limit_redis(redis, key)
        else:
            allowed, remaining, reset_in = check_send_summary_rate_limit(key)
        limit_header = SEND_SUMMARY_MAX_REQ
    elif path in ("/v1/triage/turn", "/v1/triage/feedback"):
        device_id = request.headers.get("x-device-id")
        key = build_rl_key(ip, device_id)
        redis = getattr(request.app.state, "redis", None)
        if redis:
            allowed, remaining, reset_in = await check_rate_limit_redis(redis, key)
        else:
            allowed, remaining, reset_in = check_rate_limit(key)
        limit_header = MAX_REQ
    else:
        return await call_next(request)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "reset_in_sec": reset_in},
            headers={
                "X-RateLimit-Limit": str(limit_header),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_in),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit_header)
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
app.include_router(summary_email_router, prefix="/v1", tags=["Summary Email"])
app.include_router(push_token_router, prefix="/v1", tags=["Push Token"])
app.include_router(session_router, prefix="/v1", tags=["Session (legacy)"])
app.include_router(message_router, prefix="/v1", tags=["Message (legacy)"])
app.include_router(admin_router, prefix="/v1", tags=["Admin"])
app.include_router(admin_tenants_router, prefix="/v1", tags=["Admin Tenants"])
app.include_router(admin_feedback_router, prefix="/v1", tags=["Admin Feedback"])
app.include_router(data_rights_router, prefix="/v1", tags=["Data Rights"])
# admin_v5_router carries its own prefix="/admin"; mounting under /v1
# places it at /v1/admin/* so the admin_rate_limit_middleware (which
# gates /v1/admin/*) actually protects these endpoints. Without the
# /v1 prefix the routes came out at /admin/* and bypassed rate limits.
app.include_router(admin_v5_router, prefix="/v1", tags=["Admin V5"])


@app.get("/v1/config/features")
async def features():
    """Return current feature-flag state for client-side consent and UI gating.

    Consumed by the mobile app on startup:
    - `llm_nlu_enabled` — whether to show the KVKK/AI consent banner
      before the first triage turn.
    - `llm_explain_enabled` — whether the explain-my-recommendation UI
      should surface.
    - `client_version` — min/latest/mode trio for the version-gate
      banner. The mobile app compares its own
      `Constants.expoConfig.version` against `min` and decides (based
      on `mode`) whether to warn, block, or stay silent. Rolled as a
      feature flag rather than a hard-fail semantic so ops can bake
      "warn" before flipping "block" — see CLIENT_VERSION_ENFORCEMENT
      in core/config.py.
    """
    return {
        "llm_nlu_enabled": settings.LLM_NLU_ENABLED,
        "llm_explain_enabled": settings.LLM_EXPLAIN_ENABLED,
        "client_version": {
            "min": settings.MIN_CLIENT_VERSION,
            "latest": settings.LATEST_CLIENT_VERSION,
            "mode": settings.CLIENT_VERSION_ENFORCEMENT,
            "update_url_ios": settings.CLIENT_VERSION_UPDATE_URL_IOS or None,
            "update_url_android": settings.CLIENT_VERSION_UPDATE_URL_ANDROID or None,
        },
    }


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
