"""Health endpoint: liveness, Supabase + Redis reachability with latency.

Each subsystem reports a status string. When reachable it also reports
`{name}_latency_ms` (rounded to 1 decimal) and `{name}_latency_tag`
(`ok` / `slow`) so monitoring can alert on degraded dependencies, not
just down ones. Threshold lives in `_HEALTH_SLOW_MS` (200 ms).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_and_ok():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "service" in data


def test_health_includes_subsystem_fields():
    # Even with subsystems unconfigured, the field must exist so
    # observability tools can rely on its presence.
    r = client.get("/health")
    data = r.json()
    assert "supabase" in data
    assert "redis" in data


class HealthRedisProbeTests(unittest.TestCase):
    """Redis branch: reachable / failing / slow."""

    def setUp(self):
        # Snapshot whatever app.state had so we can restore it.
        self._prev = getattr(app.state, "redis", None)

    def tearDown(self):
        app.state.redis = self._prev

    def test_redis_ok_when_ping_succeeds(self):
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(return_value=True)
        app.state.redis = mock_redis
        r = client.get("/health")
        data = r.json()
        self.assertEqual(data["redis"], "ok")
        self.assertIn("redis_latency_ms", data)
        self.assertEqual(data["redis_latency_tag"], "ok")
        self.assertGreaterEqual(data["redis_latency_ms"], 0)

    def test_redis_error_when_ping_raises(self):
        mock_redis = MagicMock()
        mock_redis.ping = AsyncMock(side_effect=RuntimeError("conn reset"))
        app.state.redis = mock_redis
        r = client.get("/health")
        data = r.json()
        self.assertEqual(data["redis"], "error")
        self.assertIn("conn reset", data["redis_error"])
        self.assertNotIn("redis_latency_ms", data)

    def test_redis_slow_tag_when_ping_takes_long(self):
        # Force a slow ping by sleeping inside the mock. We use real
        # wall-clock here instead of patching time.perf_counter because
        # httpx internals also call perf_counter — a global patch would
        # exhaust the stub iterator and crash the request.
        import asyncio as _asyncio

        async def slow_ping():
            await _asyncio.sleep(0.25)  # 250 ms — over the 200 ms threshold
            return True

        mock_redis = MagicMock()
        mock_redis.ping = slow_ping
        app.state.redis = mock_redis
        r = client.get("/health")
        data = r.json()
        self.assertEqual(data["redis"], "ok")
        self.assertGreater(data["redis_latency_ms"], 200)
        self.assertEqual(data["redis_latency_tag"], "slow")
