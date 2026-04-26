"""Idempotency-Key handling for /v1/triage/turn.

Two layers under test:
    1. ``app.idempotency`` — the cache primitive (in-memory + Redis paths).
    2. The route handler in ``app.api.routes.triage`` — header read,
       cache miss vs. hit vs. mismatch, body-hash stability.

The stub-envelope pattern matches ``test_triage_turn_e2e`` so the
triage engine doesn't actually run.
"""
from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import idempotency as idem
from app.api.routes import triage as triage_routes
from app.main import app
from app.models.schemas import Envelope, Meta


# ─── compute_body_hash ───────────────────────────────────────────────


def test_compute_body_hash_is_stable_across_dict_orderings():
    a = {"session_id": None, "locale": "tr-TR", "user_message": "x"}
    b = {"user_message": "x", "locale": "tr-TR", "session_id": None}
    assert idem.compute_body_hash(a) == idem.compute_body_hash(b)


def test_compute_body_hash_differs_for_different_bodies():
    a = {"locale": "tr-TR", "user_message": "x"}
    b = {"locale": "tr-TR", "user_message": "y"}
    assert idem.compute_body_hash(a) != idem.compute_body_hash(b)


def test_compute_body_hash_returns_hex_digest_length():
    h = idem.compute_body_hash({"k": "v"})
    assert len(h) == 64
    int(h, 16)  # must be hex


# ─── In-memory cache ─────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_idem_cache():
    # Also clear rate-limit buckets — prior tests in the suite hit
    # /v1/triage/turn 20+ times via TestClient under IP 127.0.0.1, so
    # without this we get 429-back pressure that masks idempotency
    # behavior.
    from app import rate_limit as _rl

    idem._memory_clear()
    _rl._BUCKETS.clear()
    _rl._SESSION_BUCKETS.clear()
    yield
    idem._memory_clear()
    _rl._BUCKETS.clear()
    _rl._SESSION_BUCKETS.clear()


@pytest.mark.asyncio
async def test_in_memory_lookup_miss_returns_none():
    out = await idem.lookup_cached(None, "missing-key", "deadbeef")
    assert out is None


@pytest.mark.asyncio
async def test_in_memory_store_then_lookup_hit():
    envelope = {"type": "RESULT", "payload": {"x": 1}}
    await idem.store_response(None, "k1", "h1", envelope)
    out = await idem.lookup_cached(None, "k1", "h1")
    assert out == envelope


@pytest.mark.asyncio
async def test_in_memory_lookup_with_different_body_raises_mismatch():
    envelope = {"type": "RESULT"}
    await idem.store_response(None, "k2", "h2", envelope)
    with pytest.raises(idem.IdempotencyMismatch):
        await idem.lookup_cached(None, "k2", "different-hash")


@pytest.mark.asyncio
async def test_in_memory_expiry():
    envelope = {"type": "RESULT"}
    await idem.store_response(None, "k3", "h3", envelope)
    # Force the entry to be expired without sleeping.
    body_hash, env, _ = idem._MEMORY_CACHE["k3"]
    idem._MEMORY_CACHE["k3"] = (body_hash, env, 0.0)  # expires_at in the past
    out = await idem.lookup_cached(None, "k3", "h3")
    assert out is None


@pytest.mark.asyncio
async def test_in_memory_lru_eviction():
    cap = idem._MEMORY_CACHE_MAX_ENTRIES
    # Spike the cap down so the test runs fast.
    with patch.object(idem, "_MEMORY_CACHE_MAX_ENTRIES", 3):
        for i in range(5):
            await idem.store_response(None, f"k{i}", "h", {"i": i})
        # Only the most recent 3 keys should survive.
        assert set(idem._MEMORY_CACHE) == {"k2", "k3", "k4"}


# ─── Redis cache ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_store_then_lookup_hit():
    redis = AsyncMock()
    redis._stash = {}

    async def _set(rkey, payload, ex):  # noqa: ARG001
        redis._stash[rkey] = payload

    async def _get(rkey):
        return redis._stash.get(rkey)

    redis.set = _set
    redis.get = _get
    envelope = {"type": "RESULT", "session_id": "s1"}
    await idem.store_response(redis, "k", "h", envelope)
    out = await idem.lookup_cached(redis, "k", "h")
    assert out == envelope


@pytest.mark.asyncio
async def test_redis_lookup_corrupt_entry_treated_as_miss():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="not-json")
    out = await idem.lookup_cached(redis, "k", "h")
    assert out is None


@pytest.mark.asyncio
async def test_redis_lookup_failure_falls_back_to_in_memory():
    # Pre-warm the in-memory cache, then make Redis raise on GET.
    await idem.store_response(None, "k", "h", {"type": "RESULT"})
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=RuntimeError("conn reset"))
    out = await idem.lookup_cached(redis, "k", "h")
    assert out == {"type": "RESULT"}


# ─── Route handler integration ───────────────────────────────────────


def _stub_envelope(session_id: str = "sess-1") -> Envelope:
    return Envelope(
        type="QUESTION",
        session_id=session_id,
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


def _post_turn(client, headers=None, body=None):
    if body is None:
        body = {
            "session_id": None,
            "locale": "tr-TR",
            "user_message": "Başım ağrıyor",
        }
    return client.post(
        "/v1/triage/turn",
        json=body,
        headers=headers or {},
    )


class IdempotencyRouteIntegrationTests(unittest.TestCase):
    def setUp(self):
        from app import rate_limit as _rl

        idem._memory_clear()
        _rl._BUCKETS.clear()
        _rl._SESSION_BUCKETS.clear()

    def tearDown(self):
        from app import rate_limit as _rl

        idem._memory_clear()
        _rl._BUCKETS.clear()
        _rl._SESSION_BUCKETS.clear()

    def test_no_header_runs_engine_normally(self):
        """No Idempotency-Key → no cache lookup, no cache store."""
        stub = _stub_envelope()
        engine_calls = []

        def _stub_handler(request):
            engine_calls.append(request)
            return stub

        with patch.object(
            triage_routes, "_handle_turn_supabase", side_effect=_stub_handler
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r1 = _post_turn(client)
                r2 = _post_turn(client)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # Engine ran twice — no caching without the header.
        self.assertEqual(len(engine_calls), 2)

    def test_repeat_with_same_key_and_body_returns_cached_envelope(self):
        """Idempotency-Key + same body → engine runs once; second
        request returns the cached envelope."""
        stub = _stub_envelope()
        engine_calls = []

        def _stub_handler(request):
            engine_calls.append(request)
            return stub

        with patch.object(
            triage_routes, "_handle_turn_supabase", side_effect=_stub_handler
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r1 = _post_turn(client, headers={"Idempotency-Key": "abc"})
                r2 = _post_turn(client, headers={"Idempotency-Key": "abc"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # Engine only ran once — the second call hit the cache.
        self.assertEqual(len(engine_calls), 1)
        # Both responses identical envelope.
        self.assertEqual(r1.json(), r2.json())

    def test_repeat_with_same_key_and_different_body_returns_error(self):
        """Reusing a key with a different body → IDEMPOTENCY_KEY_REUSED
        error envelope (client bug)."""
        stub = _stub_envelope()
        with patch.object(
            triage_routes, "_handle_turn_supabase", return_value=stub
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r1 = _post_turn(client, headers={"Idempotency-Key": "k"})
                self.assertEqual(r1.status_code, 200)
                r2 = _post_turn(
                    client,
                    headers={"Idempotency-Key": "k"},
                    body={
                        "session_id": None,
                        "locale": "tr-TR",
                        "user_message": "DIFFERENT MESSAGE",
                    },
                )
        # Returns 200 with ERROR envelope (existing pattern in
        # triage_turn — error states surface in the body, not HTTP).
        self.assertEqual(r2.status_code, 200)
        body = r2.json()
        self.assertEqual(body["type"], "ERROR")
        self.assertEqual(body["payload"]["code"], "IDEMPOTENCY_KEY_REUSED")

    def test_different_keys_run_engine_twice(self):
        """Different Idempotency-Key values are treated as distinct
        requests — both run the engine."""
        stub = _stub_envelope()
        engine_calls = []

        def _stub_handler(request):
            engine_calls.append(request)
            return stub

        with patch.object(
            triage_routes, "_handle_turn_supabase", side_effect=_stub_handler
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                _post_turn(client, headers={"Idempotency-Key": "k-A"})
                _post_turn(client, headers={"Idempotency-Key": "k-B"})
        self.assertEqual(len(engine_calls), 2)


if __name__ == "__main__":
    unittest.main()
