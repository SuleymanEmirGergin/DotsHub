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


# Cache clearing is handled by `_reset_process_caches` autouse fixture
# in conftest.py — no per-file teardown needed.


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
    # Cache clearing is handled by the autouse `_reset_process_caches`
    # fixture in conftest.py; pytest applies autouse fixtures to
    # unittest.TestCase methods too.

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


class IdempotencyHelperTests(unittest.TestCase):
    """The route-level helper that the 4 idempotent endpoints share.
    These tests exercise the helper in isolation so a regression in
    the helper surfaces without touching every endpoint test."""

    def setUp(self):
        from datetime import datetime, timezone

        from app.models.schemas import Meta

        # Minimal http_request stub: just need .headers and .app.state.redis.
        class _StubReq:
            def __init__(self, headers, redis=None):
                self.headers = headers
                self.app = type("A", (), {"state": type("S", (), {"redis": redis})()})()

        self._StubReq = _StubReq

        # Pydantic-ish body with model_dump(mode="json") signature.
        class _Body:
            def __init__(self, payload):
                self._payload = payload

            def model_dump(self, mode="json"):
                return self._payload

        self._Body = _Body

        def _meta():
            return Meta(
                disclaimer_tr="x",
                timestamp=datetime.now(timezone.utc),
            )

        self._meta = _meta

    def _make(self, headers, body_payload, redis=None):
        return idem.IdempotencyHelper(
            self._StubReq(headers, redis=redis),
            self._Body(body_payload),
            self._meta,
            session_id="sess-1",
        )

    def test_no_header_skips_lookup(self):
        async def _run():
            helper = self._make({}, {"x": 1})
            return await helper.check()

        out = asyncio.run(_run())
        self.assertIsNone(out)
        # Body hash must NOT be computed when there's no idempotency
        # key — saves a JSON serialise on every non-idempotent request.
        helper = self._make({}, {"x": 1})
        self.assertIsNone(helper._body_hash)

    def test_cache_hit_returns_cached_envelope(self):
        async def _run():
            # Pre-populate the in-memory cache.
            payload = {"x": 1}
            from app.idempotency import compute_body_hash
            h = compute_body_hash(payload)
            await idem.store_response(
                None,
                "k1",
                h,
                {"type": "RESULT", "session_id": "s", "payload": {}, "meta": {}},
            )
            helper = self._make(
                {"idempotency-key": "k1"}, payload
            )
            return await helper.check()

        out = asyncio.run(_run())
        self.assertIsNotNone(out)
        self.assertEqual(out.type, "RESULT")

    def test_cache_miss_returns_none(self):
        async def _run():
            helper = self._make(
                {"idempotency-key": "k-fresh"}, {"x": 99}
            )
            return await helper.check()

        out = asyncio.run(_run())
        self.assertIsNone(out)

    def test_mismatch_returns_error_envelope(self):
        async def _run():
            from app.idempotency import compute_body_hash
            # Cache under hash for body A.
            await idem.store_response(
                None,
                "k-mismatch",
                compute_body_hash({"a": 1}),
                {"type": "RESULT", "session_id": "s", "payload": {}, "meta": {}},
            )
            # Look up with body B → hash differs → IdempotencyMismatch
            # → helper returns the error envelope.
            helper = self._make(
                {"idempotency-key": "k-mismatch"}, {"a": 2}
            )
            return await helper.check()

        out = asyncio.run(_run())
        self.assertIsNotNone(out)
        self.assertEqual(out.type, "ERROR")
        self.assertEqual(out.payload["code"], "IDEMPOTENCY_KEY_REUSED")

    def test_store_writes_envelope_for_later_retrieval(self):
        async def _run():
            from app.idempotency import compute_body_hash

            from app.models.schemas import Envelope, Meta
            from datetime import datetime, timezone

            envelope = Envelope(
                type="QUOTE",
                session_id="s",
                turn_index=0,
                payload={"clinics": []},
                meta=Meta(
                    disclaimer_tr="x",
                    timestamp=datetime.now(timezone.utc),
                ),
            )
            payload = {"a": 1}
            helper = self._make(
                {"idempotency-key": "k-store"}, payload
            )
            await helper.store(envelope)
            # Verify lookup now returns the cached envelope.
            cached = await idem.lookup_cached(
                None, "k-store", compute_body_hash(payload)
            )
            return cached

        cached = asyncio.run(_run())
        self.assertIsNotNone(cached)
        self.assertEqual(cached["type"], "QUOTE")

    def test_store_without_key_is_noop(self):
        async def _run():
            from app.models.schemas import Envelope, Meta
            from datetime import datetime, timezone

            envelope = Envelope(
                type="QUOTE",
                session_id="s",
                turn_index=0,
                payload={},
                meta=Meta(
                    disclaimer_tr="x",
                    timestamp=datetime.now(timezone.utc),
                ),
            )
            helper = self._make({}, {"x": 1})
            # Must not raise even with no idempotency-key.
            await helper.store(envelope)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
