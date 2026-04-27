"""Session-based rate limit bucket — fairness layer behind shared NAT.

The IP/device bucket alone punishes multi-user NAT (cafés, university
Wi-Fi, mobile carrier CG-NAT). Adding a per-session bucket means each
ongoing triage gets its own quota in addition to the IP cap. Both must
allow for a request to pass.

Coverage targets:
    * `build_session_rl_key` — present / absent
    * in-memory bucket — allow → allow → … → deny path + prune
    * Redis bucket — happy path, count > max, ttl fallback, raise → fallback
    * middleware integration — header sets bucket, deny returns 429 with
      X-RateLimit-Bucket=session, missing header bypasses session bucket
"""
from __future__ import annotations

import asyncio
from collections import deque
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import rate_limit as rl
from app.main import app


# Cache clearing handled by `_reset_process_caches` autouse fixture in
# conftest.py — no per-file fixture needed.


# ─── build_session_rl_key ────────────────────────────────────────────

def test_build_session_rl_key_with_session():
    assert rl.build_session_rl_key("abc-123") == "sid:abc-123"


def test_build_session_rl_key_without_session_returns_anon():
    assert rl.build_session_rl_key(None) == "anon"
    assert rl.build_session_rl_key("") == "anon"


# ─── In-memory bucket ────────────────────────────────────────────────

def test_session_in_memory_first_call_allowed():
    allowed, remaining, reset_in = rl.check_session_rate_limit("sid:s1")
    assert allowed is True
    assert remaining == rl.SESSION_MAX_REQ - 1
    assert reset_in >= 1


def test_session_in_memory_denied_at_threshold():
    key = "sid:s2"
    for _ in range(rl.SESSION_MAX_REQ):
        allowed, _, _ = rl.check_session_rate_limit(key)
        assert allowed is True
    # Threshold reached — next call denied.
    allowed, remaining, reset_in = rl.check_session_rate_limit(key)
    assert allowed is False
    assert remaining == 0
    assert reset_in >= 1


def test_session_in_memory_prunes_old_entries():
    key = "sid:s3"
    # Pre-fill bucket with stale entries (> SESSION_WINDOW_SEC ago).
    import time as _t

    stale = _t.time() - rl.SESSION_WINDOW_SEC - 10
    rl._SESSION_BUCKETS[key] = deque([stale] * rl.SESSION_MAX_REQ)
    # First fresh call should prune them all and be allowed.
    allowed, remaining, _ = rl.check_session_rate_limit(key)
    assert allowed is True
    assert remaining == rl.SESSION_MAX_REQ - 1


# ─── Redis bucket ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_redis_first_call_sets_ttl():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=3600)
    allowed, remaining, reset_in = await rl.check_session_rate_limit_redis(
        redis, "sid:r1"
    )
    assert allowed is True
    assert remaining == rl.SESSION_MAX_REQ - 1
    assert reset_in == 3600
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_redis_denied_when_count_exceeds_max():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=rl.SESSION_MAX_REQ + 1)
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=120)
    redis.decr = AsyncMock()
    allowed, remaining, reset_in = await rl.check_session_rate_limit_redis(
        redis, "sid:r2"
    )
    assert allowed is False
    assert remaining == 0
    assert reset_in == 120
    redis.decr.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_redis_falls_back_to_in_memory_on_error():
    redis = AsyncMock()
    redis.incr = AsyncMock(side_effect=RuntimeError("conn reset"))
    # Fallback path should run check_session_rate_limit and allow the
    # first call.
    allowed, remaining, reset_in = await rl.check_session_rate_limit_redis(
        redis, "sid:r3"
    )
    assert allowed is True
    assert remaining == rl.SESSION_MAX_REQ - 1
    assert reset_in >= 1


# ─── Middleware integration ──────────────────────────────────────────

class _StubEnvelope:
    """Minimal stub so /v1/triage/turn returns 200 without DB."""

    @staticmethod
    def make():
        from datetime import datetime, timezone

        from app.models.schemas import Envelope, Meta

        return Envelope(
            type="QUESTION",
            session_id="sid-mid-1",
            turn_index=1,
            payload={
                "question_id": "q1",
                "canonical": "x",
                "question_tr": "test?",
                "answer_type": "yes_no",
                "choices_tr": ["yes", "no"],
                "why_asking_tr": "?",
            },
            meta=Meta(
                disclaimer_tr="x",
                timestamp=datetime.now(timezone.utc),
            ),
        )


def _post_turn(client: TestClient, headers: dict | None = None):
    return client.post(
        "/v1/triage/turn",
        json={
            "session_id": None,
            "locale": "tr-TR",
            "user_message": "test",
        },
        headers=headers or {},
    )


def test_middleware_no_session_header_skips_session_bucket():
    """A first-turn request (no X-Session-Id) must not consume the
    session bucket — that bucket only exists for continuing turns."""
    from app.api.routes import triage as triage_routes

    stub = _StubEnvelope.make()
    with patch.object(
        triage_routes, "_handle_turn_supabase", return_value=stub
    ), patch.object(triage_routes, "_has_supabase", return_value=True):
        with TestClient(app) as client:
            r = _post_turn(client)  # no header
    assert r.status_code == 200
    # No session bucket activity.
    assert "anon" not in rl._SESSION_BUCKETS
    assert all(not k.startswith("sid:") for k in rl._SESSION_BUCKETS)


def test_middleware_with_session_header_consumes_session_bucket():
    """X-Session-Id present → session bucket gets one entry per call."""
    from app.api.routes import triage as triage_routes

    stub = _StubEnvelope.make()
    with patch.object(
        triage_routes, "_handle_turn_supabase", return_value=stub
    ), patch.object(triage_routes, "_has_supabase", return_value=True):
        with TestClient(app) as client:
            r = _post_turn(client, headers={"X-Session-Id": "abc-123"})
    assert r.status_code == 200
    assert "sid:abc-123" in rl._SESSION_BUCKETS
    assert len(rl._SESSION_BUCKETS["sid:abc-123"]) == 1


def test_middleware_session_bucket_returns_429_after_limit():
    """When the per-session quota is exhausted, the next call returns
    429 with X-RateLimit-Bucket=session — a different signal from the
    IP/device 429 so the client can show a session-specific message."""
    from app.api.routes import triage as triage_routes

    # Pre-fill the session bucket past its limit.
    import time as _t

    sid = "doomed-session"
    rl._SESSION_BUCKETS[f"sid:{sid}"] = deque(
        [_t.time()] * rl.SESSION_MAX_REQ
    )

    stub = _StubEnvelope.make()
    with patch.object(
        triage_routes, "_handle_turn_supabase", return_value=stub
    ), patch.object(triage_routes, "_has_supabase", return_value=True):
        with TestClient(app) as client:
            r = _post_turn(client, headers={"X-Session-Id": sid})
    assert r.status_code == 429
    body = r.json()
    assert body["bucket"] == "session"
    assert "reset_in_sec" in body
    assert r.headers.get("X-RateLimit-Bucket") == "session"
