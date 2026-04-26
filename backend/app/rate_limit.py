"""Rate limiting: in-memory (default) or Redis for multi-instance.

Failure-mode contract
---------------------
When Redis is reachable, it's the authoritative bucket (multi-instance
consistency). When it isn't, every `*_redis` function degrades to the
in-memory bucket for that key rather than silently allowing the
request. Rationale:

  - Pure fail-open (previous behavior, returned allowed=True on any
    Redis error) lets abuse bypass rate limits completely during a
    Redis outage. That's unacceptable for a public endpoint.
  - Pure fail-closed (reject on any Redis blip) flaps user-facing 429s
    on every transient network hiccup.
  - In-memory fallback keeps per-instance enforcement going. Multi-
    instance consistency is lost during the outage (same user could
    hit N × limit if N workers are running), but the absolute cap
    per-worker stays enforced.

Every degradation is logged WARN once per bucket key, so ops sees the
split-brain in dashboards/Loki even if the user sees nothing.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import TYPE_CHECKING, Deque, Dict, Optional, Tuple

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# ─── Prometheus counter helper ─────────────────────────────────────
#
# One chokepoint for `rate_limit_hits_total{bucket,outcome}` so every
# allow/deny path becomes a single `_inc_rate_limit(...)` call at its
# return site.
#
# Double-count avoidance: the Redis variants call their in-memory
# counterpart on transient failure (see `_warn_redis_degraded_once`
# fallback path). The Redis variant does NOT increment on the fallback
# branch — the in-memory function it delegates to will. Net: exactly
# one counter bump per public rate-limit decision regardless of which
# backend actually made the call.

def _inc_rate_limit(bucket: str, outcome: str) -> None:
    """Bump `rate_limit_hits_total{bucket,outcome}`.

    Labels are bounded: four bucket names × two outcomes = 8 series,
    which keeps cardinality trivial. Import is lazy so test envs that
    don't install prometheus_client stay importable; when the import
    fails the call is silently a no-op (the scrape just won't see
    these counters).
    """
    try:
        from app.observability import rate_limit_hits_total
    except ImportError:  # pragma: no cover — prometheus_client optional
        return
    rate_limit_hits_total.labels(bucket=bucket, outcome=outcome).inc()


# Track which buckets we've already warned about to avoid log spam —
# one warn per key per process is enough to surface the Redis outage
# without drowning logs. Cleared naturally on process restart.
_REDIS_DEGRADED_WARNED: set[str] = set()


def _warn_redis_degraded_once(key: str, exc: Exception) -> None:
    if key not in _REDIS_DEGRADED_WARNED:
        _REDIS_DEGRADED_WARNED.add(key)
        logger.warning(
            "Redis rate-limit unavailable for key=%s (%s: %s). "
            "Degrading to in-memory bucket — multi-instance cap is LOST "
            "until Redis recovers; per-worker cap still enforced.",
            key, type(exc).__name__, exc,
        )

WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
MAX_REQ = int(os.getenv("RATE_LIMIT_MAX_REQ", "20"))
REDIS_KEY_PREFIX = "rl:"

# Admin API: stricter limit per IP
ADMIN_WINDOW_SEC = int(os.getenv("ADMIN_RATE_LIMIT_WINDOW_SEC", "60"))
ADMIN_MAX_REQ = int(os.getenv("ADMIN_RATE_LIMIT_MAX_REQ", "60"))
ADMIN_REDIS_KEY_PREFIX = "admin_rl:"

# Operator API (dashboard per-user): keyed by operator_id (NOT IP) so
# a noisy operator can't exhaust quota for the rest of the team. The
# super-admin (ADMIN_API_KEY) bypasses this bucket and uses the
# admin bucket above.
OPERATOR_WINDOW_SEC = int(os.getenv("OPERATOR_RATE_LIMIT_WINDOW_SEC", "60"))
OPERATOR_MAX_REQ = int(os.getenv("OPERATOR_RATE_LIMIT_MAX_REQ", "60"))
OPERATOR_REDIS_KEY_PREFIX = "operator_rl:"

# Send-summary + export-summary: shared per-IP limit (5/min)
SEND_SUMMARY_WINDOW_SEC = int(os.getenv("SEND_SUMMARY_RATE_LIMIT_WINDOW_SEC", "60"))
SEND_SUMMARY_MAX_REQ = int(os.getenv("SEND_SUMMARY_RATE_LIMIT_MAX_REQ", "5"))
SEND_SUMMARY_REDIS_KEY_PREFIX = "rl_send_summary:"

# key -> timestamps queue (in-memory fallback)
_BUCKETS: Dict[str, Deque[float]] = {}
_SEND_SUMMARY_BUCKETS: Dict[str, Deque[float]] = {}


def _prune(q: Deque[float], now: float) -> None:
    cutoff = now - WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()


def check_rate_limit(key: str) -> Tuple[bool, int, int]:
    """
    In-memory rate limit. Returns (allowed, remaining, reset_in_sec).
    """
    now = time.time()
    q = _BUCKETS.get(key)
    if q is None:
        q = deque()
        _BUCKETS[key] = q

    _prune(q, now)

    if len(q) >= MAX_REQ:
        reset_in = int(WINDOW_SEC - (now - q[0])) if q else WINDOW_SEC
        _inc_rate_limit("default", "denied")
        return False, 0, max(reset_in, 1)

    q.append(now)
    remaining = MAX_REQ - len(q)
    reset_in = int(WINDOW_SEC - (now - q[0])) if q else WINDOW_SEC
    _inc_rate_limit("default", "allowed")
    return True, remaining, max(reset_in, 1)


async def check_rate_limit_redis(redis: "Redis", key: str) -> Tuple[bool, int, int]:
    """
    Redis-backed rate limit (fixed window). Returns (allowed, remaining, reset_in_sec).
    Use when REDIS_URL is set for multi-instance consistency.
    """
    rkey = f"{REDIS_KEY_PREFIX}{key}"
    try:
        count = await redis.incr(rkey)
        if count == 1:
            await redis.expire(rkey, WINDOW_SEC)
        ttl = await redis.ttl(rkey)
        reset_in = max(ttl, 1) if ttl > 0 else WINDOW_SEC
        if count > MAX_REQ:
            await redis.decr(rkey)
            _inc_rate_limit("default", "denied")
            return False, 0, reset_in
        _inc_rate_limit("default", "allowed")
        return True, MAX_REQ - count, reset_in
    except Exception as exc:
        _warn_redis_degraded_once(f"default:{key}", exc)
        # NOTE: do not inc counter here — check_rate_limit() below will.
        return check_rate_limit(key)


def build_rl_key(ip: Optional[str], device_id: Optional[str]) -> str:
    # device varsa onu tercih et; yoksa ip
    if device_id:
        return f"d:{device_id}"
    if ip:
        return f"ip:{ip}"
    return "anon"


def build_admin_rl_key(ip: Optional[str]) -> str:
    """Admin API rate limit key: IP only."""
    return f"ip:{ip}" if ip else "anon"


def build_send_summary_rl_key(ip: Optional[str]) -> str:
    """Send-summary rate limit key: IP only."""
    return f"ip:{ip}" if ip else "anon"


def _prune_send_summary(q: Deque[float], now: float) -> None:
    cutoff = now - SEND_SUMMARY_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()


def check_send_summary_rate_limit(key: str) -> Tuple[bool, int, int]:
    """In-memory send-summary rate limit. Returns (allowed, remaining, reset_in_sec)."""
    now = time.time()
    q = _SEND_SUMMARY_BUCKETS.get(key)
    if q is None:
        q = deque()
        _SEND_SUMMARY_BUCKETS[key] = q
    _prune_send_summary(q, now)
    if len(q) >= SEND_SUMMARY_MAX_REQ:
        reset_in = int(SEND_SUMMARY_WINDOW_SEC - (now - q[0])) if q else SEND_SUMMARY_WINDOW_SEC
        _inc_rate_limit("send_summary", "denied")
        return False, 0, max(reset_in, 1)
    q.append(now)
    remaining = SEND_SUMMARY_MAX_REQ - len(q)
    reset_in = int(SEND_SUMMARY_WINDOW_SEC - (now - q[0])) if q else SEND_SUMMARY_WINDOW_SEC
    _inc_rate_limit("send_summary", "allowed")
    return True, remaining, max(reset_in, 1)


async def check_send_summary_rate_limit_redis(redis: "Redis", key: str) -> Tuple[bool, int, int]:
    """Redis-backed send-summary rate limit. Returns (allowed, remaining, reset_in_sec)."""
    rkey = f"{SEND_SUMMARY_REDIS_KEY_PREFIX}{key}"
    try:
        count = await redis.incr(rkey)
        if count == 1:
            await redis.expire(rkey, SEND_SUMMARY_WINDOW_SEC)
        ttl = await redis.ttl(rkey)
        reset_in = max(ttl, 1) if ttl > 0 else SEND_SUMMARY_WINDOW_SEC
        if count > SEND_SUMMARY_MAX_REQ:
            await redis.decr(rkey)
            _inc_rate_limit("send_summary", "denied")
            return False, 0, reset_in
        _inc_rate_limit("send_summary", "allowed")
        return True, SEND_SUMMARY_MAX_REQ - count, reset_in
    except Exception as exc:
        _warn_redis_degraded_once(f"send_summary:{key}", exc)
        # NOTE: fallback inc'd inside check_send_summary_rate_limit().
        return check_send_summary_rate_limit(key)


def check_admin_rate_limit(key: str) -> Tuple[bool, int, int]:
    """In-memory admin rate limit. Returns (allowed, remaining, reset_in_sec)."""
    now = time.time()
    q = _BUCKETS.get(key)
    if q is None:
        q = deque()
        _BUCKETS[key] = q
    cutoff = now - ADMIN_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= ADMIN_MAX_REQ:
        reset_in = int(ADMIN_WINDOW_SEC - (now - q[0])) if q else ADMIN_WINDOW_SEC
        _inc_rate_limit("admin", "denied")
        return False, 0, max(reset_in, 1)
    q.append(now)
    remaining = ADMIN_MAX_REQ - len(q)
    reset_in = int(ADMIN_WINDOW_SEC - (now - q[0])) if q else ADMIN_WINDOW_SEC
    _inc_rate_limit("admin", "allowed")
    return True, remaining, max(reset_in, 1)


async def check_admin_rate_limit_redis(redis: "Redis", key: str) -> Tuple[bool, int, int]:
    """Redis-backed admin rate limit. Returns (allowed, remaining, reset_in_sec)."""
    rkey = f"{ADMIN_REDIS_KEY_PREFIX}{key}"
    try:
        count = await redis.incr(rkey)
        if count == 1:
            await redis.expire(rkey, ADMIN_WINDOW_SEC)
        ttl = await redis.ttl(rkey)
        reset_in = max(ttl, 1) if ttl > 0 else ADMIN_WINDOW_SEC
        if count > ADMIN_MAX_REQ:
            await redis.decr(rkey)
            _inc_rate_limit("admin", "denied")
            return False, 0, reset_in
        _inc_rate_limit("admin", "allowed")
        return True, ADMIN_MAX_REQ - count, reset_in
    except Exception as exc:
        _warn_redis_degraded_once(f"admin:{key}", exc)
        # NOTE: fallback inc'd inside check_admin_rate_limit().
        return check_admin_rate_limit(key)


# ---------------------------------------------------------------------------
# Operator (dashboard per-user) rate limit
# Keyed by operator_id (NOT IP) so each operator has its own quota.
# Super-admin (ADMIN_API_KEY) skips this bucket — see admin_auth.
# ---------------------------------------------------------------------------


def build_operator_rl_key(operator_id: str | None) -> str:
    """Operator rate limit key. Falls back to "anon" when somehow
    invoked without an operator id (defensive — middleware shouldn't
    reach this path without one)."""
    return f"op:{operator_id}" if operator_id else "anon"


def check_operator_rate_limit(key: str) -> Tuple[bool, int, int]:
    """In-memory operator rate limit. Returns (allowed, remaining, reset_in_sec)."""
    now = time.time()
    q = _BUCKETS.get(key)
    if q is None:
        q = deque()
        _BUCKETS[key] = q
    cutoff = now - OPERATOR_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= OPERATOR_MAX_REQ:
        reset_in = (
            int(OPERATOR_WINDOW_SEC - (now - q[0])) if q else OPERATOR_WINDOW_SEC
        )
        _inc_rate_limit("operator", "denied")
        return False, 0, max(reset_in, 1)
    q.append(now)
    remaining = OPERATOR_MAX_REQ - len(q)
    reset_in = (
        int(OPERATOR_WINDOW_SEC - (now - q[0])) if q else OPERATOR_WINDOW_SEC
    )
    _inc_rate_limit("operator", "allowed")
    return True, remaining, max(reset_in, 1)


async def check_operator_rate_limit_redis(
    redis: "Redis", key: str
) -> Tuple[bool, int, int]:
    """Redis-backed operator rate limit."""
    rkey = f"{OPERATOR_REDIS_KEY_PREFIX}{key}"
    try:
        count = await redis.incr(rkey)
        if count == 1:
            await redis.expire(rkey, OPERATOR_WINDOW_SEC)
        ttl = await redis.ttl(rkey)
        reset_in = max(ttl, 1) if ttl > 0 else OPERATOR_WINDOW_SEC
        if count > OPERATOR_MAX_REQ:
            await redis.decr(rkey)
            _inc_rate_limit("operator", "denied")
            return False, 0, reset_in
        _inc_rate_limit("operator", "allowed")
        return True, OPERATOR_MAX_REQ - count, reset_in
    except Exception as exc:
        _warn_redis_degraded_once(f"operator:{key}", exc)
        return check_operator_rate_limit(key)


# ---------------------------------------------------------------------------
# LLM NLU rate limit — protects Wiro API quota
# Separate global bucket: limits total LLM NLU calls per minute across
# all sessions to avoid blowing the Wiro per-minute request cap.
# ---------------------------------------------------------------------------

LLM_NLU_WINDOW_SEC = int(os.getenv("LLM_NLU_RATE_LIMIT_WINDOW_SEC", "60"))
LLM_NLU_MAX_REQ = int(os.getenv("LLM_NLU_RATE_LIMIT_MAX_REQ", "30"))
LLM_NLU_REDIS_KEY_PREFIX = "rl_llm_nlu:"

# In-memory bucket — keyed by arbitrary key (typically "global" or device_id)
_LLM_NLU_BUCKETS: Dict[str, Deque[float]] = {}


def check_llm_nlu_rate_limit(key: str = "global") -> Tuple[bool, int, int]:
    """In-memory LLM NLU rate limit. Returns (allowed, remaining, reset_in_sec).

    Default key is "global" — enforces a server-wide cap on Wiro calls.
    Pass a device_id or session_id for per-user limiting.
    """
    now = time.time()
    q = _LLM_NLU_BUCKETS.get(key)
    if q is None:
        q = deque()
        _LLM_NLU_BUCKETS[key] = q

    cutoff = now - LLM_NLU_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()

    if len(q) >= LLM_NLU_MAX_REQ:
        reset_in = int(LLM_NLU_WINDOW_SEC - (now - q[0])) if q else LLM_NLU_WINDOW_SEC
        _inc_rate_limit("llm_nlu", "denied")
        return False, 0, max(reset_in, 1)

    q.append(now)
    remaining = LLM_NLU_MAX_REQ - len(q)
    reset_in = int(LLM_NLU_WINDOW_SEC - (now - q[0])) if q else LLM_NLU_WINDOW_SEC
    _inc_rate_limit("llm_nlu", "allowed")
    return True, remaining, max(reset_in, 1)


async def check_llm_nlu_rate_limit_redis(
    redis: "Redis", key: str = "global"
) -> Tuple[bool, int, int]:
    """Redis-backed LLM NLU rate limit. Returns (allowed, remaining, reset_in_sec)."""
    rkey = f"{LLM_NLU_REDIS_KEY_PREFIX}{key}"
    try:
        count = await redis.incr(rkey)
        if count == 1:
            await redis.expire(rkey, LLM_NLU_WINDOW_SEC)
        ttl = await redis.ttl(rkey)
        reset_in = max(ttl, 1) if ttl > 0 else LLM_NLU_WINDOW_SEC
        if count > LLM_NLU_MAX_REQ:
            await redis.decr(rkey)
            _inc_rate_limit("llm_nlu", "denied")
            return False, 0, reset_in
        _inc_rate_limit("llm_nlu", "allowed")
        return True, LLM_NLU_MAX_REQ - count, reset_in
    except Exception as exc:
        _warn_redis_degraded_once(f"llm_nlu:{key}", exc)
        # NOTE: fallback inc'd inside check_llm_nlu_rate_limit().
        return check_llm_nlu_rate_limit(key)


# ---------------------------------------------------------------------------
# Session-based rate limit — fairness layer behind shared NAT
# ---------------------------------------------------------------------------
#
# IP-only buckets punish multi-user NAT (cafés, university Wi-Fi, mobile
# carrier CG-NAT): one heavy user can starve everyone else's quota.
# Solution: keep the IP bucket for abuse defence (creating sessions) but
# add a per-session bucket so each ongoing triage gets its own quota
# regardless of how many users share the egress IP.
#
# Both buckets must allow for a request to pass:
#   - first turn (no session_id) → only IP bucket applies
#   - continuing turn (X-Session-Id header) → both IP + session apply
# This keeps the IP cap as a session-creation throttle and stops a single
# session from looping infinitely (e.g. broken client retry).
#
# Default window is intentionally longer than the IP window (1 h vs 1 m)
# because a real triage spans many turns over minutes; a per-minute
# session cap would deny legitimate slow users.

SESSION_WINDOW_SEC = int(os.getenv("SESSION_RATE_LIMIT_WINDOW_SEC", "3600"))
SESSION_MAX_REQ = int(os.getenv("SESSION_RATE_LIMIT_MAX_REQ", "30"))
SESSION_REDIS_KEY_PREFIX = "rl_session:"

_SESSION_BUCKETS: Dict[str, Deque[float]] = {}


def build_session_rl_key(session_id: Optional[str]) -> str:
    """Session rate-limit key. Returns 'sid:<id>' or 'anon' for None.

    Callers should only invoke session rate limiting when a session_id
    is present — the 'anon' fallback exists so the function is total
    (always returns a string), but enforcing on it would lump every
    sessionless request into one shared bucket.
    """
    return f"sid:{session_id}" if session_id else "anon"


def check_session_rate_limit(key: str) -> Tuple[bool, int, int]:
    """In-memory session rate limit. Returns (allowed, remaining, reset_in_sec)."""
    now = time.time()
    q = _SESSION_BUCKETS.get(key)
    if q is None:
        q = deque()
        _SESSION_BUCKETS[key] = q
    cutoff = now - SESSION_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= SESSION_MAX_REQ:
        reset_in = int(SESSION_WINDOW_SEC - (now - q[0])) if q else SESSION_WINDOW_SEC
        _inc_rate_limit("session", "denied")
        return False, 0, max(reset_in, 1)
    q.append(now)
    remaining = SESSION_MAX_REQ - len(q)
    reset_in = int(SESSION_WINDOW_SEC - (now - q[0])) if q else SESSION_WINDOW_SEC
    _inc_rate_limit("session", "allowed")
    return True, remaining, max(reset_in, 1)


async def check_session_rate_limit_redis(
    redis: "Redis", key: str
) -> Tuple[bool, int, int]:
    """Redis-backed session rate limit. Returns (allowed, remaining, reset_in_sec)."""
    rkey = f"{SESSION_REDIS_KEY_PREFIX}{key}"
    try:
        count = await redis.incr(rkey)
        if count == 1:
            await redis.expire(rkey, SESSION_WINDOW_SEC)
        ttl = await redis.ttl(rkey)
        reset_in = max(ttl, 1) if ttl > 0 else SESSION_WINDOW_SEC
        if count > SESSION_MAX_REQ:
            await redis.decr(rkey)
            _inc_rate_limit("session", "denied")
            return False, 0, reset_in
        _inc_rate_limit("session", "allowed")
        return True, SESSION_MAX_REQ - count, reset_in
    except Exception as exc:
        _warn_redis_degraded_once(f"session:{key}", exc)
        # NOTE: fallback inc'd inside check_session_rate_limit().
        return check_session_rate_limit(key)
