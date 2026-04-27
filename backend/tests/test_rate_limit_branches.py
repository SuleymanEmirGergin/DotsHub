"""Branch coverage for app.rate_limit.

The module has eight near-identical functions across four limit
buckets (triage / admin / send-summary / LLM NLU) in two flavours
(in-memory, Redis). Each flavour has the same branch shape:

  in-memory:
    - bucket missing → allocate + allow
    - bucket below threshold → allow
    - bucket at threshold → deny (returns reset_in)
    - empty queue edge on reset_in calc → `else` branch

  Redis:
    - count == 1 → set TTL (first request in window)
    - ttl > 0 → reset_in = ttl
    - ttl <= 0 → reset_in = WINDOW_SEC fallback
    - count > max → decrement + return denied
    - Redis raises → fail-open (return True)

Plus the key builders (`build_rl_key`, `build_admin_rl_key`,
`build_send_summary_rl_key`) each have three branches:
device_id preferred → ip fallback → anon.

Tests use `unittest.mock.AsyncMock` to simulate Redis, so we stay
100% deterministic + run offline.
"""
from __future__ import annotations

import asyncio
from collections import deque
from unittest.mock import AsyncMock

import pytest

from app import rate_limit as rl


# Bucket clearing handled by `_reset_process_caches` autouse fixture
# in conftest.py.


# ─── Key builders ───────────────────────────────────────────────────

def test_build_rl_key_prefers_device_id():
    assert rl.build_rl_key(ip="1.2.3.4", device_id="dev-1") == "d:dev-1"


def test_build_rl_key_falls_back_to_ip_when_device_absent():
    assert rl.build_rl_key(ip="1.2.3.4", device_id=None) == "ip:1.2.3.4"


def test_build_rl_key_returns_anon_when_both_missing():
    assert rl.build_rl_key(ip=None, device_id=None) == "anon"


def test_build_admin_rl_key_variants():
    assert rl.build_admin_rl_key("1.2.3.4") == "ip:1.2.3.4"
    assert rl.build_admin_rl_key(None) == "anon"


def test_build_send_summary_rl_key_variants():
    assert rl.build_send_summary_rl_key("5.6.7.8") == "ip:5.6.7.8"
    assert rl.build_send_summary_rl_key(None) == "anon"


# ─── _prune / _prune_send_summary ───────────────────────────────────

def test_prune_drops_entries_older_than_window():
    q = deque([0.0, 1.0])  # both very old
    rl._prune(q, now=100.0 + rl.WINDOW_SEC)
    assert len(q) == 0


def test_prune_send_summary_drops_old():
    q = deque([0.0])
    rl._prune_send_summary(q, now=100.0 + rl.SEND_SUMMARY_WINDOW_SEC)
    assert len(q) == 0


# ─── In-memory: check_rate_limit ────────────────────────────────────

def test_in_memory_allows_first_request_and_allocates_bucket():
    allowed, remaining, reset_in = rl.check_rate_limit("k1")
    assert allowed is True
    assert remaining == rl.MAX_REQ - 1
    assert reset_in >= 1
    assert "k1" in rl._BUCKETS


def test_in_memory_denies_when_bucket_is_at_max():
    # Pre-load the bucket to exactly MAX_REQ timestamps in the window.
    import time as _time
    now = _time.time()
    rl._BUCKETS["k2"] = deque([now] * rl.MAX_REQ)
    allowed, remaining, reset_in = rl.check_rate_limit("k2")
    assert allowed is False
    assert remaining == 0
    assert reset_in >= 1


def test_in_memory_empty_queue_edge_uses_window_sec():
    # After pruning wipes every entry, the `if q else WINDOW_SEC`
    # branch kicks in. Pre-load with one stale entry so pruning
    # empties the queue BEFORE the append + reset calc.
    rl._BUCKETS["k3"] = deque([0.0])  # stale
    allowed, _, reset_in = rl.check_rate_limit("k3")
    assert allowed is True
    # reset_in should be a positive int — not blow up on an empty queue
    # during the calculation.
    assert reset_in >= 1


# ─── In-memory: check_send_summary_rate_limit ───────────────────────

def test_in_memory_send_summary_allows_first_request():
    allowed, remaining, reset_in = rl.check_send_summary_rate_limit("ip:1")
    assert allowed is True
    assert remaining == rl.SEND_SUMMARY_MAX_REQ - 1
    assert reset_in >= 1


def test_in_memory_send_summary_denies_at_max():
    import time as _time
    now = _time.time()
    rl._SEND_SUMMARY_BUCKETS["ip:2"] = deque([now] * rl.SEND_SUMMARY_MAX_REQ)
    allowed, remaining, _ = rl.check_send_summary_rate_limit("ip:2")
    assert allowed is False
    assert remaining == 0


def test_in_memory_send_summary_empty_queue_edge():
    rl._SEND_SUMMARY_BUCKETS["ip:3"] = deque([0.0])
    allowed, _, reset_in = rl.check_send_summary_rate_limit("ip:3")
    assert allowed is True
    assert reset_in >= 1


# ─── In-memory: check_admin_rate_limit ──────────────────────────────

def test_in_memory_admin_allows_first_request():
    allowed, remaining, _ = rl.check_admin_rate_limit("ip:admin")
    assert allowed is True
    assert remaining == rl.ADMIN_MAX_REQ - 1


def test_in_memory_admin_denies_at_max():
    import time as _time
    now = _time.time()
    rl._BUCKETS["ip:admin2"] = deque([now] * rl.ADMIN_MAX_REQ)
    allowed, remaining, _ = rl.check_admin_rate_limit("ip:admin2")
    assert allowed is False
    assert remaining == 0


def test_in_memory_admin_empty_queue_edge():
    rl._BUCKETS["ip:admin3"] = deque([0.0])
    allowed, _, reset_in = rl.check_admin_rate_limit("ip:admin3")
    assert allowed is True
    assert reset_in >= 1


# ─── In-memory: check_operator_rate_limit + key builder ─────────────


def test_build_operator_rl_key_variants():
    """Operator bucket is keyed by operator id (NOT IP); falls back
    to "anon" when somehow invoked without an id (defensive)."""
    assert rl.build_operator_rl_key("OP-123") == "op:OP-123"
    assert rl.build_operator_rl_key(None) == "anon"
    assert rl.build_operator_rl_key("") == "anon"


def test_in_memory_operator_allows_first_request():
    allowed, remaining, _ = rl.check_operator_rate_limit("op:first")
    assert allowed is True
    assert remaining == rl.OPERATOR_MAX_REQ - 1


def test_in_memory_operator_denies_at_max():
    import time as _time
    now = _time.time()
    rl._BUCKETS["op:max"] = deque([now] * rl.OPERATOR_MAX_REQ)
    allowed, remaining, _ = rl.check_operator_rate_limit("op:max")
    assert allowed is False
    assert remaining == 0


def test_in_memory_operator_empty_queue_edge():
    """Edge: bucket has a single timestamp older than the window cutoff;
    request is allowed but reset_in fallback path runs."""
    rl._BUCKETS["op:edge"] = deque([0.0])
    allowed, _, reset_in = rl.check_operator_rate_limit("op:edge")
    assert allowed is True
    assert reset_in >= 1


# ─── In-memory: check_llm_nlu_rate_limit ────────────────────────────

def test_in_memory_llm_nlu_default_global_key_works():
    # Default `key="global"` branch.
    allowed, remaining, _ = rl.check_llm_nlu_rate_limit()
    assert allowed is True
    assert remaining == rl.LLM_NLU_MAX_REQ - 1
    assert "global" in rl._LLM_NLU_BUCKETS


def test_in_memory_llm_nlu_custom_key_creates_new_bucket():
    rl.check_llm_nlu_rate_limit("device-xyz")
    assert "device-xyz" in rl._LLM_NLU_BUCKETS


def test_in_memory_llm_nlu_denies_at_max():
    import time as _time
    now = _time.time()
    rl._LLM_NLU_BUCKETS["global"] = deque([now] * rl.LLM_NLU_MAX_REQ)
    allowed, remaining, _ = rl.check_llm_nlu_rate_limit()
    assert allowed is False
    assert remaining == 0


def test_in_memory_llm_nlu_empty_queue_edge():
    rl._LLM_NLU_BUCKETS["global"] = deque([0.0])
    allowed, _, reset_in = rl.check_llm_nlu_rate_limit()
    assert allowed is True
    assert reset_in >= 1


# ─── Redis flavour helpers ──────────────────────────────────────────

def _make_redis(incr_value, ttl=45):
    """Mock Redis with incr + expire + ttl + decr as AsyncMocks."""
    redis = AsyncMock()
    redis.incr.return_value = incr_value
    redis.expire.return_value = True
    redis.ttl.return_value = ttl
    redis.decr.return_value = incr_value - 1
    return redis


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ─── Redis: check_rate_limit_redis ──────────────────────────────────

def test_redis_rate_limit_first_request_sets_ttl():
    redis = _make_redis(incr_value=1, ttl=60)
    allowed, remaining, reset_in = _run(rl.check_rate_limit_redis(redis, "k"))
    assert allowed is True
    assert remaining == rl.MAX_REQ - 1
    assert reset_in == 60
    redis.expire.assert_called_once_with(f"{rl.REDIS_KEY_PREFIX}k", rl.WINDOW_SEC)


def test_redis_rate_limit_subsequent_request_skips_expire():
    redis = _make_redis(incr_value=2, ttl=30)
    _run(rl.check_rate_limit_redis(redis, "k"))
    redis.expire.assert_not_called()


def test_redis_rate_limit_ttl_zero_falls_back_to_window():
    redis = _make_redis(incr_value=1, ttl=0)
    _, _, reset_in = _run(rl.check_rate_limit_redis(redis, "k"))
    assert reset_in == rl.WINDOW_SEC


def test_redis_rate_limit_over_max_decrements_and_denies():
    redis = _make_redis(incr_value=rl.MAX_REQ + 1, ttl=30)
    allowed, remaining, _ = _run(rl.check_rate_limit_redis(redis, "k"))
    assert allowed is False
    assert remaining == 0
    redis.decr.assert_called_once()


def test_redis_rate_limit_fail_open_on_exception():
    redis = AsyncMock()
    redis.incr.side_effect = ConnectionError("redis down")
    allowed, remaining, reset_in = _run(rl.check_rate_limit_redis(redis, "k"))
    assert allowed is True
    assert remaining == rl.MAX_REQ - 1
    assert reset_in == rl.WINDOW_SEC


# ─── Redis: check_admin_rate_limit_redis ────────────────────────────

def test_redis_admin_first_request_sets_ttl():
    redis = _make_redis(incr_value=1, ttl=60)
    allowed, remaining, reset_in = _run(rl.check_admin_rate_limit_redis(redis, "k"))
    assert allowed is True
    assert remaining == rl.ADMIN_MAX_REQ - 1
    redis.expire.assert_called_once_with(f"{rl.ADMIN_REDIS_KEY_PREFIX}k", rl.ADMIN_WINDOW_SEC)


def test_redis_admin_subsequent_request_skips_expire():
    redis = _make_redis(incr_value=5, ttl=40)
    _run(rl.check_admin_rate_limit_redis(redis, "k"))
    redis.expire.assert_not_called()


def test_redis_admin_ttl_zero_falls_back_to_window():
    redis = _make_redis(incr_value=1, ttl=0)
    _, _, reset_in = _run(rl.check_admin_rate_limit_redis(redis, "k"))
    assert reset_in == rl.ADMIN_WINDOW_SEC


def test_redis_admin_over_max_denies():
    redis = _make_redis(incr_value=rl.ADMIN_MAX_REQ + 1, ttl=30)
    allowed, remaining, _ = _run(rl.check_admin_rate_limit_redis(redis, "k"))
    assert allowed is False
    assert remaining == 0


def test_redis_admin_fail_open_on_exception():
    redis = AsyncMock()
    redis.incr.side_effect = RuntimeError("redis down")
    allowed, _, _ = _run(rl.check_admin_rate_limit_redis(redis, "k"))
    assert allowed is True


# ─── Redis: check_operator_rate_limit_redis ─────────────────────────


def test_redis_operator_first_request_sets_ttl():
    redis = _make_redis(incr_value=1, ttl=60)
    allowed, remaining, _ = _run(
        rl.check_operator_rate_limit_redis(redis, "op:1")
    )
    assert allowed is True
    assert remaining == rl.OPERATOR_MAX_REQ - 1
    redis.expire.assert_called_once_with(
        f"{rl.OPERATOR_REDIS_KEY_PREFIX}op:1", rl.OPERATOR_WINDOW_SEC
    )


def test_redis_operator_subsequent_request_skips_expire():
    redis = _make_redis(incr_value=5, ttl=40)
    _run(rl.check_operator_rate_limit_redis(redis, "op:1"))
    redis.expire.assert_not_called()


def test_redis_operator_ttl_zero_falls_back_to_window():
    redis = _make_redis(incr_value=1, ttl=0)
    _, _, reset_in = _run(rl.check_operator_rate_limit_redis(redis, "op:1"))
    assert reset_in == rl.OPERATOR_WINDOW_SEC


def test_redis_operator_over_max_denies():
    redis = _make_redis(incr_value=rl.OPERATOR_MAX_REQ + 1, ttl=30)
    allowed, remaining, _ = _run(
        rl.check_operator_rate_limit_redis(redis, "op:1")
    )
    assert allowed is False
    assert remaining == 0


def test_redis_operator_fail_open_on_exception():
    """Redis blip degrades to in-memory bucket -- request allowed
    (assuming in-memory hasn't already been hammered)."""
    redis = AsyncMock()
    redis.incr.side_effect = RuntimeError("redis down")
    allowed, _, _ = _run(rl.check_operator_rate_limit_redis(redis, "op:1"))
    assert allowed is True


# ─── In-memory: check_session_rate_limit + key builder ──────────────


def test_build_session_rl_key_variants():
    """Session bucket is keyed by session_id (NOT IP); 'anon'
    fallback for missing id keeps the function total but should not
    be exercised in production paths."""
    assert rl.build_session_rl_key("S-1") == "sid:S-1"
    assert rl.build_session_rl_key(None) == "anon"
    assert rl.build_session_rl_key("") == "anon"


def test_in_memory_session_allows_first_request():
    allowed, remaining, _ = rl.check_session_rate_limit("sid:first")
    assert allowed is True
    assert remaining == rl.SESSION_MAX_REQ - 1


def test_in_memory_session_denies_at_max():
    import time as _time
    now = _time.time()
    rl._SESSION_BUCKETS["sid:max"] = deque([now] * rl.SESSION_MAX_REQ)
    allowed, remaining, _ = rl.check_session_rate_limit("sid:max")
    assert allowed is False
    assert remaining == 0


def test_in_memory_session_empty_queue_edge():
    """Bucket has one stale timestamp (older than the window cutoff)
    -- pruned during check, request allowed; reset_in fallback path
    runs."""
    rl._SESSION_BUCKETS["sid:edge"] = deque([0.0])
    allowed, _, reset_in = rl.check_session_rate_limit("sid:edge")
    assert allowed is True
    assert reset_in >= 1


# ─── Redis: check_session_rate_limit_redis ──────────────────────────


def test_redis_session_first_request_sets_ttl():
    redis = _make_redis(incr_value=1, ttl=60)
    allowed, remaining, _ = _run(
        rl.check_session_rate_limit_redis(redis, "sid:1")
    )
    assert allowed is True
    assert remaining == rl.SESSION_MAX_REQ - 1
    redis.expire.assert_called_once_with(
        f"{rl.SESSION_REDIS_KEY_PREFIX}sid:1", rl.SESSION_WINDOW_SEC
    )


def test_redis_session_subsequent_request_skips_expire():
    redis = _make_redis(incr_value=5, ttl=40)
    _run(rl.check_session_rate_limit_redis(redis, "sid:1"))
    redis.expire.assert_not_called()


def test_redis_session_ttl_zero_falls_back_to_window():
    redis = _make_redis(incr_value=1, ttl=0)
    _, _, reset_in = _run(rl.check_session_rate_limit_redis(redis, "sid:1"))
    assert reset_in == rl.SESSION_WINDOW_SEC


def test_redis_session_over_max_denies():
    redis = _make_redis(incr_value=rl.SESSION_MAX_REQ + 1, ttl=30)
    allowed, remaining, _ = _run(
        rl.check_session_rate_limit_redis(redis, "sid:1")
    )
    assert allowed is False
    assert remaining == 0


def test_redis_session_fail_open_on_exception():
    redis = AsyncMock()
    redis.incr.side_effect = RuntimeError("redis down")
    allowed, _, _ = _run(rl.check_session_rate_limit_redis(redis, "sid:1"))
    assert allowed is True


# ─── Redis: check_send_summary_rate_limit_redis ─────────────────────

def test_redis_send_summary_first_request_sets_ttl():
    redis = _make_redis(incr_value=1, ttl=60)
    allowed, remaining, _ = _run(rl.check_send_summary_rate_limit_redis(redis, "k"))
    assert allowed is True
    assert remaining == rl.SEND_SUMMARY_MAX_REQ - 1


def test_redis_send_summary_subsequent_skips_expire():
    redis = _make_redis(incr_value=2, ttl=40)
    _run(rl.check_send_summary_rate_limit_redis(redis, "k"))
    redis.expire.assert_not_called()


def test_redis_send_summary_ttl_zero_falls_back():
    redis = _make_redis(incr_value=1, ttl=0)
    _, _, reset_in = _run(rl.check_send_summary_rate_limit_redis(redis, "k"))
    assert reset_in == rl.SEND_SUMMARY_WINDOW_SEC


def test_redis_send_summary_over_max_denies():
    redis = _make_redis(incr_value=rl.SEND_SUMMARY_MAX_REQ + 1, ttl=20)
    allowed, remaining, _ = _run(rl.check_send_summary_rate_limit_redis(redis, "k"))
    assert allowed is False
    assert remaining == 0


def test_redis_send_summary_fail_open_on_exception():
    redis = AsyncMock()
    redis.incr.side_effect = OSError("boom")
    allowed, _, _ = _run(rl.check_send_summary_rate_limit_redis(redis, "k"))
    assert allowed is True


# ─── Redis: check_llm_nlu_rate_limit_redis ──────────────────────────

def test_redis_llm_nlu_default_global_first_request():
    redis = _make_redis(incr_value=1, ttl=60)
    allowed, remaining, _ = _run(rl.check_llm_nlu_rate_limit_redis(redis))
    assert allowed is True
    assert remaining == rl.LLM_NLU_MAX_REQ - 1
    redis.expire.assert_called_once()


def test_redis_llm_nlu_subsequent_skips_expire():
    redis = _make_redis(incr_value=5, ttl=30)
    _run(rl.check_llm_nlu_rate_limit_redis(redis, "device-x"))
    redis.expire.assert_not_called()


def test_redis_llm_nlu_ttl_zero_falls_back():
    redis = _make_redis(incr_value=1, ttl=0)
    _, _, reset_in = _run(rl.check_llm_nlu_rate_limit_redis(redis))
    assert reset_in == rl.LLM_NLU_WINDOW_SEC


def test_redis_llm_nlu_over_max_denies():
    redis = _make_redis(incr_value=rl.LLM_NLU_MAX_REQ + 1, ttl=10)
    allowed, remaining, _ = _run(rl.check_llm_nlu_rate_limit_redis(redis))
    assert allowed is False
    assert remaining == 0


def test_redis_llm_nlu_fail_open_on_exception():
    redis = AsyncMock()
    redis.incr.side_effect = TimeoutError("slow")
    allowed, _, _ = _run(rl.check_llm_nlu_rate_limit_redis(redis))
    assert allowed is True
