"""Clinic registry — hybrid Supabase / JSON loader.

Read order
    1. Supabase ``health_tourism_clinics`` table (when SUPABASE_URL is
       configured AND the table exists with at least one row).
    2. ``app/data/clinics.json`` — seed data; used by local dev, CI,
       and as the failure fallback when Supabase is unreachable.

Caching
    The active clinic list is cached at module level for the lifetime
    of the process. Production redeploys are weekly; ops that need a
    same-process cache flush call ``clear_cache()`` (used by tests).
    A short TTL would add latency to every quote request without a
    proportional benefit — partner clinic data does not change every
    minute.

Why hybrid (not Supabase-only)
    Local dev shouldn't need a database. CI shouldn't need a database.
    A Supabase outage shouldn't take quotes offline — JSON keeps a
    static fallback for the partner list we know about. Ops gets the
    'add a clinic without a code release' benefit when the database
    is up, and zero new failure modes when it's down.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "clinics.json"
_TABLE_NAME = "health_tourism_clinics"


# ─── Caches ──────────────────────────────────────────────────────────
#
# Two caches — JSON load (cheap, deterministic) and Supabase fetch
# (network call). Both module-level so the lifetime is the worker
# process. clear_cache() is exposed for tests.

_JSON_CACHE: Optional[list[dict[str, Any]]] = None
_SUPABASE_CACHE: Optional[list[dict[str, Any]]] = None


def clear_cache() -> None:
    """Test-only helper: drop both layers' caches. Production callers
    rely on process-restart cycles instead."""
    global _JSON_CACHE, _SUPABASE_CACHE
    _JSON_CACHE = None
    _SUPABASE_CACHE = None


# ─── JSON loader ─────────────────────────────────────────────────────


def _load_from_json() -> list[dict[str, Any]]:
    global _JSON_CACHE
    if _JSON_CACHE is not None:
        return _JSON_CACHE
    with _DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "clinics" not in data:
        raise ValueError(
            f"clinics.json: expected top-level 'clinics' key, got {list(data)}"
        )
    _JSON_CACHE = list(data["clinics"])
    return _JSON_CACHE


# ─── Supabase loader ─────────────────────────────────────────────────


def _supabase_configured() -> bool:
    """Cheap check before importing the supabase client. Misconfigured
    envs (one var set, the other not) count as 'not configured' so the
    JSON fallback runs cleanly."""
    return bool(
        os.environ.get("SUPABASE_URL")
        and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )


def _row_to_clinic_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a database row to the same shape the rest of the
    codebase expects (mirrors clinics.json entries).

    ``metadata`` jsonb holds any extra fields the JSON catalog might
    carry that haven't been promoted to columns yet — surface them at
    the top level so callers don't need to know about the indirection.
    """
    out = dict(row)
    metadata = out.pop("metadata", None) or {}
    if isinstance(metadata, dict):
        for k, v in metadata.items():
            out.setdefault(k, v)
    # Drop columns the rest of the codebase doesn't read — keeps the
    # in-memory shape tight and forward-compat (new columns won't leak
    # until promoted explicitly).
    for column in ("created_at", "updated_at", "is_active"):
        out.pop(column, None)
    return out


def _load_from_supabase() -> Optional[list[dict[str, Any]]]:
    """Fetch active clinics from Supabase. Returns None on any failure
    (network, schema mismatch, table missing). Caller falls back to
    JSON in that case."""
    global _SUPABASE_CACHE
    if _SUPABASE_CACHE is not None:
        return _SUPABASE_CACHE
    try:
        from app.supabase_client import get_supabase
        sb = get_supabase()
        result = (
            sb.table(_TABLE_NAME)
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        rows = getattr(result, "data", None) or []
    except Exception as exc:
        logger.info(
            "clinic_registry.supabase_unavailable: %s — using JSON fallback",
            exc,
        )
        return None
    if not rows:
        # Empty table — treat as 'not yet seeded' and use JSON. This
        # is the path on a freshly migrated project where seed_*.py
        # hasn't run yet.
        logger.info(
            "clinic_registry.supabase_empty: 0 active rows — using JSON fallback"
        )
        return None
    _SUPABASE_CACHE = [_row_to_clinic_dict(r) for r in rows]
    return _SUPABASE_CACHE


# ─── Public API ──────────────────────────────────────────────────────


def all_clinics() -> list[dict[str, Any]]:
    if _supabase_configured():
        rows = _load_from_supabase()
        if rows is not None:
            return rows
    return _load_from_json()


def get_clinic(clinic_id: str) -> Optional[dict[str, Any]]:
    for c in all_clinics():
        if c.get("id") == clinic_id:
            return c
    return None


def clinics_for_procedure(procedure_id: str) -> list[dict[str, Any]]:
    """Return every clinic whose ``procedures_offered`` contains the id."""
    return [
        c for c in all_clinics()
        if procedure_id in c.get("procedures_offered", [])
    ]


def maps_url(clinic: dict[str, Any]) -> Optional[str]:
    """Build a Google Maps URL from clinic lat/lon. None if no coordinates."""
    lat, lon = clinic.get("lat"), clinic.get("lon")
    if lat is None or lon is None:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
