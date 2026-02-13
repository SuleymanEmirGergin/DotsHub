"""Rate limiting: in-memory (default) or Redis for multi-instance."""
from __future__ import annotations

import os
import time
from collections import deque
from typing import TYPE_CHECKING, Deque, Dict, Optional, Tuple

if TYPE_CHECKING:
    from redis.asyncio import Redis

WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
MAX_REQ = int(os.getenv("RATE_LIMIT_MAX_REQ", "20"))
REDIS_KEY_PREFIX = "rl:"

# Admin API: stricter limit per IP
ADMIN_WINDOW_SEC = int(os.getenv("ADMIN_RATE_LIMIT_WINDOW_SEC", "60"))
ADMIN_MAX_REQ = int(os.getenv("ADMIN_RATE_LIMIT_MAX_REQ", "60"))
ADMIN_REDIS_KEY_PREFIX = "admin_rl:"

# key -> timestamps queue (in-memory fallback)
_BUCKETS: Dict[str, Deque[float]] = {}


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
        return False, 0, max(reset_in, 1)

    q.append(now)
    remaining = MAX_REQ - len(q)
    reset_in = int(WINDOW_SEC - (now - q[0])) if q else WINDOW_SEC
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
            return False, 0, reset_in
        return True, MAX_REQ - count, reset_in
    except Exception:
        # On Redis error, fall back to allowing (fail open) or use in-memory in middleware
        return True, MAX_REQ - 1, WINDOW_SEC


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
        return False, 0, max(reset_in, 1)
    q.append(now)
    remaining = ADMIN_MAX_REQ - len(q)
    reset_in = int(ADMIN_WINDOW_SEC - (now - q[0])) if q else ADMIN_WINDOW_SEC
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
            return False, 0, reset_in
        return True, ADMIN_MAX_REQ - count, reset_in
    except Exception:
        return True, ADMIN_MAX_REQ - 1, ADMIN_WINDOW_SEC
