"""Database utilities for Supabase integration."""
from __future__ import annotations

import os
import hashlib
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlparse

from supabase import create_client, Client
from app.core.config import settings

SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_SERVICE_ROLE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")


def _ensure_no_proxy_for_host(url: str) -> None:
    host = urlparse(url).hostname
    if not host:
        return
    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    entries = [item.strip() for item in existing.split(",") if item.strip()]
    if host not in entries:
        entries.append(host)
        merged = ",".join(entries)
        os.environ["NO_PROXY"] = merged
        os.environ["no_proxy"] = merged


_ensure_no_proxy_for_host(SUPABASE_URL)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

IP_HASH_SALT = settings.IP_HASH_SALT


def hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    h = hashlib.sha256((IP_HASH_SALT + ip).encode("utf-8")).hexdigest()
    return h


@contextmanager
def _timed_supabase(operation: str) -> Iterator[None]:
    """Measure a Supabase call's latency + outcome.

    Wraps the `with _timed_supabase("op_name"): supabase.table(...)`
    pattern so `supabase_db_calls_total` + `supabase_db_latency_seconds`
    pick up every wrapped invocation. Exceptions re-raise unchanged
    after the error counter fires — the block is observability only,
    it MUST NOT change call semantics.

    Prometheus is an optional runtime dep (the app runs fine without
    it in a local-dev scenario), so metric lookup is wrapped in a
    defensive import. A missing metrics module means the block is
    effectively a no-op timer; latency is still measured locally but
    not recorded.

    Usage:

        with _timed_supabase("triage_sessions.upsert"):
            supabase.table("triage_sessions").upsert(row).execute()

    Operation naming convention: `<table>.<verb>` (e.g.
    `triage_events.insert`). Keeps the `operation` label
    cardinality bounded + readable in the Grafana query.
    """
    try:
        from app.observability import (
            supabase_db_calls_total,
            supabase_db_latency_seconds,
        )
    except ImportError:  # pragma: no cover — prometheus_client optional
        supabase_db_calls_total = None  # type: ignore[assignment]
        supabase_db_latency_seconds = None  # type: ignore[assignment]

    def _record(outcome: str, t0: float) -> None:
        if supabase_db_calls_total is not None:
            supabase_db_calls_total.labels(
                operation=operation, outcome=outcome
            ).inc()
        if supabase_db_latency_seconds is not None:
            supabase_db_latency_seconds.labels(
                operation=operation
            ).observe(time.monotonic() - t0)

    t0 = time.monotonic()
    try:
        yield
    except BaseException:
        _record("error", t0)
        raise
    else:
        _record("success", t0)


def upsert_session(session_id: str, row: Dict[str, Any]) -> None:
    # updated_at otomatik değilse burada set et
    row["session_id"] = session_id
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    with _timed_supabase("triage_sessions.upsert"):
        supabase.table("triage_sessions").upsert(row).execute()


def insert_event(session_id: str, event: str, data: Optional[Dict[str, Any]] = None) -> None:
    with _timed_supabase("triage_events.insert"):
        supabase.table("triage_events").insert({
            "session_id": session_id,
            "event": event,
            "data": data or {},
        }).execute()


def insert_feedback(row: Dict[str, Any]) -> None:
    with _timed_supabase("triage_feedback.insert"):
        supabase.table("triage_feedback").insert(row).execute()
