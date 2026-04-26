"""Idempotency-Key support for `/v1/triage/turn`.

Why this exists
    Mobile clients retry on flaky networks. Without an idempotency
    layer, a retry that lands after the original succeeded creates a
    duplicate triage event in Supabase (and emits a duplicate envelope
    to the user). The client can't tell the difference between "request
    timed out, server didn't run" and "request timed out, server ran
    but the response packet got dropped" — so safe-by-default retries
    cause real downstream issues (double session events, double
    feedback rows, double LLM-NLU calls billed).

The contract
    The client sends ``Idempotency-Key: <opaque-string>`` on each
    request; on retry it sends the SAME key. The server caches
    ``(key, body-hash) → envelope`` for ``IDEMPOTENCY_TTL_SEC``. On a
    repeat with the same body, the cached envelope is returned without
    re-running the triage engine. On a repeat with a different body,
    that's a client bug — we surface it as a 422-style error rather
    than overwriting the cache (silent overwrite would mask retry
    misuse).

Storage
    Redis when ``app.state.redis`` is configured (multi-instance
    consistent). In-memory dict fallback otherwise — single-instance,
    bounded by an LRU cap so a malicious client spamming distinct keys
    can't exhaust memory.

Hashing
    Body hash is SHA-256 of the canonicalised JSON (sorted keys, no
    whitespace). Stable across Python versions and JSON libraries.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


IDEMPOTENCY_TTL_SEC = int(os.getenv("IDEMPOTENCY_TTL_SEC", "300"))  # 5 min
IDEMPOTENCY_REDIS_KEY_PREFIX = "idem:"
# In-memory cap — enough headroom for normal retry traffic, low enough
# that a flood of distinct keys can't OOM the worker. LRU eviction.
_MEMORY_CACHE_MAX_ENTRIES = int(os.getenv("IDEMPOTENCY_MEMORY_MAX", "1024"))


# ─── Body hashing ─────────────────────────────────────────────────────

def compute_body_hash(body: Any) -> str:
    """Return a stable SHA-256 hex digest of the request body.

    `sort_keys=True` + `separators=(",", ":")` makes the encoding
    deterministic across runs and platforms; without it, dict
    ordering or whitespace differences would produce different
    hashes for semantically identical payloads.
    """
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─── In-memory store ──────────────────────────────────────────────────
#
# OrderedDict gives us O(1) move-to-end + popitem(last=False) for LRU
# eviction. Each entry is `(body_hash, envelope_json, expires_at)` so
# the lookup can verify the body matched and prune expired entries
# without a background sweeper.

_MEMORY_CACHE: "OrderedDict[str, Tuple[str, dict, float]]" = OrderedDict()


def _memory_lookup(key: str) -> Optional[Tuple[str, dict]]:
    entry = _MEMORY_CACHE.get(key)
    if entry is None:
        return None
    body_hash, envelope, expires_at = entry
    if time.time() >= expires_at:
        # Lazy expiry — drop and signal miss.
        _MEMORY_CACHE.pop(key, None)
        return None
    # Fresh hit → mark as recently used for LRU.
    _MEMORY_CACHE.move_to_end(key)
    return body_hash, envelope


def _memory_store(key: str, body_hash: str, envelope: dict) -> None:
    expires_at = time.time() + IDEMPOTENCY_TTL_SEC
    _MEMORY_CACHE[key] = (body_hash, envelope, expires_at)
    _MEMORY_CACHE.move_to_end(key)
    while len(_MEMORY_CACHE) > _MEMORY_CACHE_MAX_ENTRIES:
        _MEMORY_CACHE.popitem(last=False)


def _memory_clear() -> None:
    """Test-only helper. Production code never calls this."""
    _MEMORY_CACHE.clear()


# ─── Redis store ──────────────────────────────────────────────────────

async def _redis_lookup(
    redis: "Redis", key: str
) -> Optional[Tuple[str, dict]]:
    rkey = f"{IDEMPOTENCY_REDIS_KEY_PREFIX}{key}"
    try:
        raw = await redis.get(rkey)
    except Exception as exc:  # network blip → degrade to in-memory
        logger.warning(
            "idempotency: Redis GET failed for key=%s (%s); using in-memory",
            key, type(exc).__name__,
        )
        return _memory_lookup(key)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        return payload["body_hash"], payload["envelope"]
    except (json.JSONDecodeError, KeyError, TypeError):
        # Corrupt entry — treat as a miss; the next store will overwrite.
        return None


async def _redis_store(
    redis: "Redis", key: str, body_hash: str, envelope: dict
) -> None:
    rkey = f"{IDEMPOTENCY_REDIS_KEY_PREFIX}{key}"
    payload = json.dumps(
        {"body_hash": body_hash, "envelope": envelope},
        ensure_ascii=False,
        default=str,
    )
    try:
        await redis.set(rkey, payload, ex=IDEMPOTENCY_TTL_SEC)
    except Exception as exc:
        logger.warning(
            "idempotency: Redis SET failed for key=%s (%s); using in-memory",
            key, type(exc).__name__,
        )
        _memory_store(key, body_hash, envelope)


# ─── Public API ───────────────────────────────────────────────────────

class IdempotencyMismatch(Exception):
    """Raised when the client reuses an Idempotency-Key with a
    different request body. This is a client-side bug — the key is
    supposed to be unique per logical request, so seeing the same key
    with a different body means the client is either generating keys
    incorrectly or replaying a stale request."""


async def lookup_cached(
    redis: Optional["Redis"], key: str, body_hash: str
) -> Optional[dict]:
    """Return the cached envelope for a key/body pair, or None.

    Raises ``IdempotencyMismatch`` when the key is cached but the body
    hash differs — caller should respond with a client error.
    """
    if redis is not None:
        cached = await _redis_lookup(redis, key)
    else:
        cached = _memory_lookup(key)
    if cached is None:
        return None
    cached_hash, envelope = cached
    if cached_hash != body_hash:
        raise IdempotencyMismatch(
            f"Idempotency-Key '{key}' was reused with a different body"
        )
    return envelope


async def store_response(
    redis: Optional["Redis"], key: str, body_hash: str, envelope: dict
) -> None:
    """Cache the envelope for a key/body pair. TTL = IDEMPOTENCY_TTL_SEC."""
    if redis is not None:
        await _redis_store(redis, key, body_hash, envelope)
    else:
        _memory_store(key, body_hash, envelope)


# ─── Route-level helper ──────────────────────────────────────────────
#
# Every health-tourism + triage-turn endpoint repeats the same 30
# lines of plumbing (read header, hash body, lookup, mismatch error,
# store after success). A FastAPI decorator can't wrap the route
# cleanly — the framework introspects parameters at registration time
# and a generic wrapper either loses the signature or has to manually
# replay it. A helper class is the next-cleanest abstraction: 3 line
# call site (init / check / store) and identical semantics across
# endpoints.
#
# Usage:
#     idem = IdempotencyHelper(http_request, request, _make_meta, session_id)
#     early = await idem.check()
#     if early is not None:
#         return early
#     envelope = ...build envelope...
#     await idem.store(envelope)
#     return envelope


class IdempotencyHelper:
    """Encapsulate the Idempotency-Key cache lookup + store cycle.

    Hashes the body once (lazily) so lookup + store don't double-hash.
    Caller decides what envelope to return on mismatch by passing a
    ``meta_factory`` and ``session_id`` — keeping the helper agnostic
    of the endpoint-specific disclaimer text.
    """

    def __init__(
        self,
        http_request,  # fastapi.Request — left untyped to avoid import here
        body_model,
        meta_factory,
        session_id: str,
        mismatch_message_tr: str = (
            "Idempotency-Key aynı ama istek gövdesi farklı."
        ),
    ):
        self._http_request = http_request
        self._body_model = body_model
        self._meta_factory = meta_factory
        self._session_id = session_id
        self._mismatch_message_tr = mismatch_message_tr
        self.idempotency_key: Optional[str] = http_request.headers.get(
            "idempotency-key"
        )
        self._redis = getattr(http_request.app.state, "redis", None)
        self._body_hash_cache: Optional[str] = None

    @property
    def _body_hash(self) -> Optional[str]:
        """Compute the body hash once. Returns None when there's no
        idempotency-key (no point hashing) or when serialisation fails
        (caller should not cache)."""
        if self.idempotency_key is None:
            return None
        if self._body_hash_cache is not None:
            return self._body_hash_cache
        try:
            self._body_hash_cache = compute_body_hash(
                self._body_model.model_dump(mode="json")
            )
        except Exception:  # noqa: BLE001 — hash failure is recoverable
            return None
        return self._body_hash_cache

    def _build_mismatch_envelope(self):
        """Late import of Envelope — avoids a top-level cycle since
        this module is imported by routes that import schemas."""
        from app.models.schemas import Envelope

        return Envelope(
            type="ERROR",
            session_id=self._session_id,
            turn_index=0,
            payload={
                "code": "IDEMPOTENCY_KEY_REUSED",
                "message_tr": self._mismatch_message_tr,
                "retryable": False,
            },
            meta=self._meta_factory(),
        )

    async def check(self):
        """Return an Envelope to short-circuit the route, or None
        to continue. Two short-circuit cases:
          - cache hit on (key, body_hash) → return the cached Envelope
          - cache hit on key with DIFFERENT body → IDEMPOTENCY_KEY_REUSED
            error envelope (client bug)

        Lookup failures (Redis down, etc.) are logged WARN and treated
        as a miss — the route runs as if no idempotency was requested.
        """
        if self.idempotency_key is None or self._body_hash is None:
            return None
        try:
            cached = await lookup_cached(
                self._redis, self.idempotency_key, self._body_hash
            )
        except IdempotencyMismatch:
            return self._build_mismatch_envelope()
        except Exception as exc:  # noqa: BLE001 — degrade to miss
            logger.warning(
                "idempotency.lookup_failed: %s; proceeding without cache", exc
            )
            return None
        if cached is None:
            return None
        from app.models.schemas import Envelope
        return Envelope.model_validate(cached)

    async def store(self, envelope) -> None:
        """Cache the envelope for next-attempt retrieval. Cache write
        failures are non-fatal — the response has already been built;
        a missed cache only costs a re-run on the next retry."""
        if self.idempotency_key is None or self._body_hash is None:
            return
        try:
            await store_response(
                self._redis,
                self.idempotency_key,
                self._body_hash,
                envelope.model_dump(mode="json"),
            )
        except Exception as exc:  # noqa: BLE001 — non-fatal
            logger.warning("idempotency.store_failed: %s", exc)
