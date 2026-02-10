"""Database utilities for Supabase integration."""
from __future__ import annotations

import os
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional
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


def upsert_session(session_id: str, row: Dict[str, Any]) -> None:
    # updated_at otomatik değilse burada set et
    row["session_id"] = session_id
    row["updated_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("triage_sessions").upsert(row).execute()


def insert_event(session_id: str, event: str, data: Optional[Dict[str, Any]] = None) -> None:
    supabase.table("triage_events").insert({
        "session_id": session_id,
        "event": event,
        "data": data or {},
    }).execute()


def insert_feedback(row: Dict[str, Any]) -> None:
    supabase.table("triage_feedback").insert(row).execute()
