"""/health endpoint — liveness + Supabase + Redis latency probes.

The endpoint never fails the request: a probe failure is recorded in
the response body, not in the HTTP status. Liveness is the process
answering at all. Each subsystem reports a status string and (when
reachable) a `latency_ms` reading + ok/slow tag, so monitoring can
alert on degraded — not just down — dependencies.

Threshold (200 ms) is loose enough that intra-region hops don't trip
it but tight enough to surface a pegged Supabase or Redis instance
before users notice.
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import FastAPI, Request

from app.core.config import settings


_HEALTH_SLOW_MS = 200


def _tag_latency(ms: Optional[float]) -> str:
    if ms is None:
        return "unknown"
    return "slow" if ms > _HEALTH_SLOW_MS else "ok"


async def health_check(request: Request):
    out = {"status": "ok", "service": "dotshub-api", "version": "4.0.0"}

    # ─── Supabase probe ─────────────────────────────────────────────
    if settings.SUPABASE_URL and "xxxx" not in settings.SUPABASE_URL:
        try:
            import httpx
            t0 = time.perf_counter()
            r = httpx.get(
                f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/",
                headers={"apikey": settings.SUPABASE_SERVICE_ROLE_KEY or ""},
                timeout=2.0,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            reachable = r.status_code in (200, 401)
            out["supabase"] = (
                "ok" if reachable else f"status_{r.status_code}"
            )
            out["supabase_latency_ms"] = round(elapsed_ms, 1)
            if reachable:
                out["supabase_latency_tag"] = _tag_latency(elapsed_ms)
        except Exception as e:
            out["supabase"] = "error"
            out["supabase_error"] = str(e)[:200]
    else:
        out["supabase"] = "not_configured"

    # ─── Redis probe ────────────────────────────────────────────────
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        try:
            t0 = time.perf_counter()
            await redis_client.ping()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            out["redis"] = "ok"
            out["redis_latency_ms"] = round(elapsed_ms, 1)
            out["redis_latency_tag"] = _tag_latency(elapsed_ms)
        except Exception as e:
            out["redis"] = "error"
            out["redis_error"] = str(e)[:200]
    elif getattr(settings, "REDIS_URL", None):
        out["redis"] = "unavailable"
    else:
        out["redis"] = "not_configured"

    return out


def register_health(app: FastAPI) -> None:
    app.get("/health")(health_check)
