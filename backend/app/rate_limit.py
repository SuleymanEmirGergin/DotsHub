"""In-memory rate limiting for API endpoints."""
from __future__ import annotations

import os
import time
from collections import deque
from typing import Deque, Dict, Tuple, Optional


WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
MAX_REQ = int(os.getenv("RATE_LIMIT_MAX_REQ", "20"))

# key -> timestamps queue
_BUCKETS: Dict[str, Deque[float]] = {}


def _prune(q: Deque[float], now: float) -> None:
    cutoff = now - WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()


def check_rate_limit(key: str) -> Tuple[bool, int, int]:
    """
    returns (allowed, remaining, reset_in_sec)
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


def build_rl_key(ip: Optional[str], device_id: Optional[str]) -> str:
    # device varsa onu tercih et; yoksa ip
    if device_id:
        return f"d:{device_id}"
    if ip:
        return f"ip:{ip}"
    return "anon"
