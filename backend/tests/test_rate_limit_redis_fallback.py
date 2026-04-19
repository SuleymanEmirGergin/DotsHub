"""Tests for Redis-outage degradation in rate_limit.

Scope: every `*_redis` function must degrade to the in-memory bucket
when Redis raises, NOT silently allow the request. Pre-fix behavior
returned (True, MAX-1, WINDOW) which let abuse bypass limits entirely
during a Redis outage.

The tests simulate Redis failure by passing a mock client whose
.incr() raises. A correctly-degraded path:
  - First call: returns (True, MAX-1, _)  [same as in-memory first hit]
  - After MAX+1 calls to the same key: returns (False, 0, _)  [rejected]
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app import rate_limit


class FailingRedis:
    """Minimal stand-in for redis.asyncio.Redis whose every op raises.

    AsyncMock with side_effect=Exception would work too, but a named
    class makes the test intent obvious from a stack trace.
    """

    async def incr(self, key):
        raise ConnectionError("mock redis down")

    async def expire(self, key, ttl):
        raise ConnectionError("mock redis down")

    async def ttl(self, key):
        raise ConnectionError("mock redis down")

    async def decr(self, key):
        raise ConnectionError("mock redis down")


def _reset_state():
    """Clear in-memory buckets + the dedup warn set between tests."""
    rate_limit._BUCKETS.clear()
    rate_limit._SEND_SUMMARY_BUCKETS.clear()
    rate_limit._LLM_NLU_BUCKETS.clear()
    rate_limit._REDIS_DEGRADED_WARNED.clear()


class DefaultBucketDegradationTests(unittest.TestCase):
    """check_rate_limit_redis — triage/feedback endpoint limit."""

    def setUp(self):
        _reset_state()

    def test_first_call_allowed_under_degradation(self):
        """First request against a fresh bucket must succeed."""
        redis = FailingRedis()
        allowed, remaining, _ = asyncio.run(
            rate_limit.check_rate_limit_redis(redis, "ip:1.2.3.4")
        )
        self.assertTrue(allowed)
        self.assertEqual(remaining, rate_limit.MAX_REQ - 1)

    def test_exhausting_in_memory_bucket_rejects(self):
        """After MAX_REQ calls, subsequent calls must be rejected —
        proves the degradation actually enforces a cap."""
        redis = FailingRedis()
        key = "ip:exhaust"
        # Consume the whole bucket.
        for _ in range(rate_limit.MAX_REQ):
            asyncio.run(rate_limit.check_rate_limit_redis(redis, key))
        # Next call should be rejected.
        allowed, remaining, _ = asyncio.run(
            rate_limit.check_rate_limit_redis(redis, key)
        )
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_degradation_emits_single_warning(self):
        """Ops sees the split-brain once per key, not per request."""
        redis = FailingRedis()
        with self.assertLogs("app.rate_limit", level="WARNING") as cm:
            for _ in range(3):
                asyncio.run(rate_limit.check_rate_limit_redis(redis, "ip:warn"))
        warn_lines = [r for r in cm.output if "Redis rate-limit unavailable" in r]
        self.assertEqual(len(warn_lines), 1)


class SendSummaryBucketDegradationTests(unittest.TestCase):
    """Same contract for the tighter send-summary limit."""

    def setUp(self):
        _reset_state()

    def test_first_call_allowed_then_rejects_after_limit(self):
        redis = FailingRedis()
        key = "ip:sum"
        for _ in range(rate_limit.SEND_SUMMARY_MAX_REQ):
            allowed, _, _ = asyncio.run(
                rate_limit.check_send_summary_rate_limit_redis(redis, key)
            )
            self.assertTrue(allowed)
        allowed, _, _ = asyncio.run(
            rate_limit.check_send_summary_rate_limit_redis(redis, key)
        )
        self.assertFalse(allowed)


class AdminBucketDegradationTests(unittest.TestCase):
    """Admin endpoint limit."""

    def setUp(self):
        _reset_state()

    def test_degradation_enforces_admin_cap(self):
        redis = FailingRedis()
        key = "ip:admin"
        # Admin's MAX is typically higher — use a smaller mocked cap
        # to keep the test fast without dragging 60 calls.
        with patch.object(rate_limit, "ADMIN_MAX_REQ", 3):
            for _ in range(3):
                allowed, _, _ = asyncio.run(
                    rate_limit.check_admin_rate_limit_redis(redis, key)
                )
                self.assertTrue(allowed)
            allowed, _, _ = asyncio.run(
                rate_limit.check_admin_rate_limit_redis(redis, key)
            )
            self.assertFalse(allowed)


class LLMNLUBucketDegradationTests(unittest.TestCase):
    """Protects Wiro quota — critical that this doesn't fail-open."""

    def setUp(self):
        _reset_state()

    def test_degradation_enforces_llm_nlu_cap(self):
        redis = FailingRedis()
        with patch.object(rate_limit, "LLM_NLU_MAX_REQ", 2):
            for _ in range(2):
                allowed, _, _ = asyncio.run(
                    rate_limit.check_llm_nlu_rate_limit_redis(redis, "global")
                )
                self.assertTrue(allowed)
            allowed, _, _ = asyncio.run(
                rate_limit.check_llm_nlu_rate_limit_redis(redis, "global")
            )
            self.assertFalse(allowed)


class RedisHappyPathTests(unittest.TestCase):
    """Cover the untested-in-baseline Redis happy paths for the
    send_summary, admin, and llm_nlu variants. The default-bucket
    happy path is covered by test_rate_limit_redis_happy_path_unaffected
    in HappyPathStillWorksTests below."""

    def setUp(self):
        _reset_state()

    def _happy_redis(self, count_returns: int = 1, ttl_returns: int = 60):
        redis = MagicMock()
        redis.incr = AsyncMock(return_value=count_returns)
        redis.expire = AsyncMock(return_value=True)
        redis.ttl = AsyncMock(return_value=ttl_returns)
        redis.decr = AsyncMock(return_value=count_returns - 1)
        return redis

    def test_send_summary_redis_first_call_sets_ttl(self):
        """count == 1 branch sets the expire — verifies the early
        setup path of check_send_summary_rate_limit_redis."""
        redis = self._happy_redis(count_returns=1)
        allowed, remaining, reset = asyncio.run(
            rate_limit.check_send_summary_rate_limit_redis(redis, "ip:sum-first")
        )
        self.assertTrue(allowed)
        self.assertEqual(remaining, rate_limit.SEND_SUMMARY_MAX_REQ - 1)
        self.assertEqual(reset, 60)
        redis.expire.assert_awaited_once()

    def test_send_summary_redis_over_limit_returns_false(self):
        """count > MAX branch: decrement + rejection."""
        redis = self._happy_redis(
            count_returns=rate_limit.SEND_SUMMARY_MAX_REQ + 1,
            ttl_returns=30,
        )
        allowed, remaining, _ = asyncio.run(
            rate_limit.check_send_summary_rate_limit_redis(redis, "ip:sum-over")
        )
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        redis.decr.assert_awaited_once()

    def test_admin_redis_first_call_sets_ttl(self):
        redis = self._happy_redis(count_returns=1)
        allowed, remaining, _ = asyncio.run(
            rate_limit.check_admin_rate_limit_redis(redis, "ip:admin-first")
        )
        self.assertTrue(allowed)
        self.assertEqual(remaining, rate_limit.ADMIN_MAX_REQ - 1)

    def test_admin_redis_over_limit_returns_false(self):
        redis = self._happy_redis(
            count_returns=rate_limit.ADMIN_MAX_REQ + 1,
        )
        allowed, _, _ = asyncio.run(
            rate_limit.check_admin_rate_limit_redis(redis, "ip:admin-over")
        )
        self.assertFalse(allowed)
        redis.decr.assert_awaited_once()

    def test_llm_nlu_redis_over_limit(self):
        """Wiro quota guard — critical that this rejects when we're
        over cap. Protects credit / SLA."""
        redis = self._happy_redis(
            count_returns=rate_limit.LLM_NLU_MAX_REQ + 1,
        )
        allowed, _, _ = asyncio.run(
            rate_limit.check_llm_nlu_rate_limit_redis(redis, "global")
        )
        self.assertFalse(allowed)
        redis.decr.assert_awaited_once()

    def test_redis_ttl_zero_falls_back_to_window_default(self):
        """TTL=0 (key just expired between incr and ttl) should still
        return a sane reset_in — the max() guards against 0-division
        confusion in the UI header."""
        redis = MagicMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        redis.ttl = AsyncMock(return_value=0)
        redis.decr = AsyncMock(return_value=0)
        _, _, reset = asyncio.run(
            rate_limit.check_rate_limit_redis(redis, "ip:ttl-zero")
        )
        self.assertEqual(reset, rate_limit.WINDOW_SEC)


class InMemoryOverflowTests(unittest.TestCase):
    """Drive the in-memory buckets past their cap directly — confirms
    the rejection branches in the pure-sync helpers. Important because
    the Redis-fail fallback routes through these."""

    def setUp(self):
        _reset_state()

    def test_admin_in_memory_bucket_rejects_after_limit(self):
        """ADMIN_MAX_REQ is typically 60 — patch it smaller for speed."""
        with patch.object(rate_limit, "ADMIN_MAX_REQ", 2):
            for _ in range(2):
                allowed, _, _ = rate_limit.check_admin_rate_limit("ip:admin-mem")
                self.assertTrue(allowed)
            allowed, remaining, _ = rate_limit.check_admin_rate_limit("ip:admin-mem")
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_send_summary_in_memory_bucket_rejects_after_limit(self):
        with patch.object(rate_limit, "SEND_SUMMARY_MAX_REQ", 2):
            for _ in range(2):
                allowed, _, _ = rate_limit.check_send_summary_rate_limit("ip:sum-mem")
                self.assertTrue(allowed)
            allowed, _, _ = rate_limit.check_send_summary_rate_limit("ip:sum-mem")
        self.assertFalse(allowed)

    def test_llm_nlu_in_memory_bucket_rejects_after_limit(self):
        with patch.object(rate_limit, "LLM_NLU_MAX_REQ", 2):
            for _ in range(2):
                allowed, _, _ = rate_limit.check_llm_nlu_rate_limit("global")
                self.assertTrue(allowed)
            allowed, _, _ = rate_limit.check_llm_nlu_rate_limit("global")
        self.assertFalse(allowed)


class HappyPathStillWorksTests(unittest.TestCase):
    """Regression guard: the degradation path must not break the
    Redis-reachable happy path. A passing mock counts.incr()/ttl() must
    still round-trip without touching the in-memory bucket or the warn
    set."""

    def setUp(self):
        _reset_state()

    def test_redis_happy_path_unaffected(self):
        redis = MagicMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        redis.ttl = AsyncMock(return_value=60)
        redis.decr = AsyncMock(return_value=0)

        allowed, remaining, reset = asyncio.run(
            rate_limit.check_rate_limit_redis(redis, "ip:happy")
        )
        self.assertTrue(allowed)
        self.assertEqual(remaining, rate_limit.MAX_REQ - 1)
        self.assertEqual(reset, 60)
        # No warning emitted, no in-memory state touched.
        self.assertEqual(rate_limit._REDIS_DEGRADED_WARNED, set())
        self.assertNotIn("ip:happy", rate_limit._BUCKETS)


if __name__ == "__main__":
    unittest.main()
