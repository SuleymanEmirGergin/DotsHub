"""Supabase client singleton — used by feedback & dashboard-facing endpoints."""

import os
from urllib.parse import urlparse
from supabase import create_client, Client
from app.core.config import settings


def _ensure_no_proxy_for_host(url: str) -> None:
    """Avoid broken local proxy settings for direct Supabase calls."""
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


def get_supabase() -> Client:
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in backend/.env")
    _ensure_no_proxy_for_host(url)
    return create_client(url, key)
