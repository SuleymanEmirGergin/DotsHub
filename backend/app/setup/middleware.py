"""Middleware registration + rolling-window observers + rate-limit dispatch.

Why one module
    All four middleware (request-id, 5xx monitor, rate-limit, admin
    rate-limit) plus their helpers and the rate-limit dispatch table
    are tightly coupled — they share the rolling-window observer, the
    settings flags, and the rate_limit module's bucket primitives. A
    cross-module call graph would force public re-exports of names
    that exist purely for one specific middleware. Keeping them in one
    module means the file is `register_middlewares(app) → app sees
    every middleware in order` and nothing else escapes.

Registration order matters
    Starlette applies middleware LIFO on the request path: the last
    `add_middleware()` call wraps the OUTERMOST layer. This module
    keeps the historical order:
        CORSMiddleware         (outermost on request)
        SecurityHeadersMiddleware
        CapabilityGateMiddleware
        request_id_middleware
        http_5xx_monitor_middleware
        rate_limit_middleware
        admin_rate_limit_middleware (innermost — wraps the route)
"""
from __future__ import annotations

import logging
import time
from collections import Counter, deque
from threading import Lock
from typing import NamedTuple, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.request_id import generate_request_id, set_request_id
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.rate_limit import (
    ADMIN_MAX_REQ,
    MAX_REQ,
    SEND_SUMMARY_MAX_REQ,
    SESSION_MAX_REQ,
    build_admin_rl_key,
    build_rl_key,
    build_send_summary_rl_key,
    build_session_rl_key,
    check_admin_rate_limit,
    check_admin_rate_limit_redis,
    check_rate_limit,
    check_rate_limit_redis,
    check_send_summary_rate_limit,
    check_send_summary_rate_limit_redis,
    check_session_rate_limit,
    check_session_rate_limit_redis,
)
from app.version_gating import CapabilityGateMiddleware

logger = logging.getLogger(__name__)


# ── HTTP 5xx + rate-limit rejection observers ───────────────────────
#
# Rolling-window state is module-global per worker — same trade-off as
# the original main.py inline version: small memory footprint, lost on
# restart, no inter-worker view. Operators get the per-worker view via
# Prometheus rate-limit metrics; these observers exist solely to fire
# webhook alerts on rate spikes via app.notifier.

_HTTP_LOCK = Lock()
_HTTP_EVENTS: deque = deque()
_HTTP_LAST_ALERT_TS: float = 0.0

_RL_LOCK = Lock()
_RL_EVENTS: deque = deque()
_RL_LAST_ALERT_TS: float = 0.0


def _rate_limit_observe(bucket: str, key: str, allowed: bool) -> None:
    if not getattr(settings, "RATE_LIMIT_ALERT_ENABLED", True):
        return
    window = int(getattr(settings, "RATE_LIMIT_ALERT_WINDOW", 100))
    min_dec = int(getattr(settings, "RATE_LIMIT_ALERT_MIN_DECISIONS", 30))
    threshold = float(getattr(settings, "RATE_LIMIT_ALERT_THRESHOLD_PCT", 10.0))
    cooldown = float(getattr(settings, "RATE_LIMIT_ALERT_COOLDOWN_SEC", 600))

    global _RL_LAST_ALERT_TS
    with _RL_LOCK:
        _RL_EVENTS.append((bool(allowed), bucket, key or ""))
        while len(_RL_EVENTS) > window:
            _RL_EVENTS.popleft()
        n = len(_RL_EVENTS)
        if n < min_dec:
            return
        rejections = sum(1 for a, _b, _k in _RL_EVENTS if not a)
        rejection_pct = 100.0 * rejections / n
        if rejection_pct < threshold:
            return
        now = time.monotonic()
        if now - _RL_LAST_ALERT_TS < cooldown:
            return
        _RL_LAST_ALERT_TS = now
        pairs = Counter((b, k) for a, b, k in _RL_EVENTS if not a)
        top_bucket, top_key = pairs.most_common(1)[0][0] if pairs else (None, None)

    try:
        from app.notifier import send_rate_limit_alert

        send_rate_limit_alert(
            rejection_rate_pct=rejection_pct,
            window_size=n,
            top_bucket=top_bucket,
            top_key=top_key,
            threshold_pct=threshold,
        )
    except Exception:
        pass


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
        now = time.monotonic()
        if now - _HTTP_LAST_ALERT_TS < cooldown:
            return
        _HTTP_LAST_ALERT_TS = now
        pairs = Counter((p, s) for b, s, p in _HTTP_EVENTS if b)
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


# ── Rate-limit dispatch table (R5) ──────────────────────────────────


class _RLBucket(NamedTuple):
    name: str
    key_builder: object  # Callable[[Request], str]
    sync_check: object
    async_check: object
    limit: int
    also_session: bool


def _ip_of(request) -> Optional[str]:
    return request.client.host if request.client else None


def _send_summary_key(request) -> str:
    return build_send_summary_rl_key(_ip_of(request))


def _default_key(request) -> str:
    return build_rl_key(_ip_of(request), request.headers.get("x-device-id"))


_RATE_LIMITS: dict[str, _RLBucket] = {
    "/v1/triage/send-summary": _RLBucket(
        "send_summary", _send_summary_key,
        check_send_summary_rate_limit, check_send_summary_rate_limit_redis,
        SEND_SUMMARY_MAX_REQ, also_session=False,
    ),
    "/v1/triage/export-summary": _RLBucket(
        "send_summary", _send_summary_key,
        check_send_summary_rate_limit, check_send_summary_rate_limit_redis,
        SEND_SUMMARY_MAX_REQ, also_session=False,
    ),
    "/v1/triage/turn": _RLBucket(
        "default", _default_key,
        check_rate_limit, check_rate_limit_redis,
        MAX_REQ, also_session=True,
    ),
    "/v1/triage/stream": _RLBucket(
        "default", _default_key,
        check_rate_limit, check_rate_limit_redis,
        MAX_REQ, also_session=True,
    ),
    "/v1/triage/feedback": _RLBucket(
        "default", _default_key,
        check_rate_limit, check_rate_limit_redis,
        MAX_REQ, also_session=True,
    ),
    "/v1/quote": _RLBucket(
        "default", _default_key,
        check_rate_limit, check_rate_limit_redis,
        MAX_REQ, also_session=True,
    ),
    "/v1/quote/itinerary": _RLBucket(
        "default", _default_key,
        check_rate_limit, check_rate_limit_redis,
        MAX_REQ, also_session=True,
    ),
    "/v1/quote/lead": _RLBucket(
        "default", _default_key,
        check_rate_limit, check_rate_limit_redis,
        MAX_REQ, also_session=True,
    ),
}


# ── Middleware coroutines ───────────────────────────────────────────


async def request_id_middleware(request, call_next):
    """Generate request_id, set in context, add X-Request-ID to response."""
    rid = request.headers.get("X-Request-ID") or generate_request_id()
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


async def http_5xx_monitor_middleware(request, call_next):
    """Observe every response; surface 5xx rate spikes as webhook alerts."""
    try:
        response = await call_next(request)
        _http_observe(response.status_code, request.scope.get("path", "?"))
        return response
    except Exception:
        _http_observe(500, request.scope.get("path", "?"))
        raise


async def rate_limit_middleware(request, call_next):
    """Apply rate limit per-path via the _RATE_LIMITS dispatch table.

    Each entry knows its bucket name, how to build the cache key from
    the request, which check function to use (sync vs Redis), the
    limit constant for X-RateLimit-Limit, and whether to enforce the
    per-session fairness layer on top.
    """
    path = request.scope.get("path", "")
    cfg = _RATE_LIMITS.get(path)
    if cfg is None:
        return await call_next(request)

    redis = getattr(request.app.state, "redis", None)
    key = cfg.key_builder(request)
    if redis:
        allowed, remaining, reset_in = await cfg.async_check(redis, key)
    else:
        allowed, remaining, reset_in = cfg.sync_check(key)

    if allowed and cfg.also_session:
        session_id = request.headers.get("x-session-id")
        if session_id:
            session_key = build_session_rl_key(session_id)
            if redis:
                s_allowed, s_remaining, s_reset_in = (
                    await check_session_rate_limit_redis(redis, session_key)
                )
            else:
                s_allowed, s_remaining, s_reset_in = check_session_rate_limit(
                    session_key
                )
            _rate_limit_observe("session", session_key, s_allowed)
            if not s_allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded (session)",
                        "reset_in_sec": s_reset_in,
                        "bucket": "session",
                    },
                    headers={
                        "X-RateLimit-Limit": str(SESSION_MAX_REQ),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(s_reset_in),
                        "X-RateLimit-Bucket": "session",
                    },
                )

    _rate_limit_observe(cfg.name, key, allowed)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "reset_in_sec": reset_in},
            headers={
                "X-RateLimit-Limit": str(cfg.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_in),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(cfg.limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_in)
    return response


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
    _rate_limit_observe("admin", key, allowed)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Admin API rate limit exceeded",
                "reset_in_sec": reset_in,
            },
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


# ── Public API: register everything in the right order ──────────────


def register_middlewares(app: FastAPI) -> None:
    """Mount every middleware in the order main.py historically used.

    Starlette applies middleware LIFO, so the FIRST add_middleware()
    call ends up OUTERMOST on the request path. We deliberately keep
    CORS first so cross-origin browser calls clear the policy gate
    before any other layer touches them.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-RateLimit-Bucket",
        ],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CapabilityGateMiddleware)

    app.middleware("http")(request_id_middleware)
    app.middleware("http")(http_5xx_monitor_middleware)
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(admin_rate_limit_middleware)
