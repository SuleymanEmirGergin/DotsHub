"""Shared admin authentication helpers. API key → tenant_id (Faz 1: admin tenant-aware)."""

from __future__ import annotations

import json
from fastapi import HTTPException

from app.core.config import settings


def _tenant_admin_keys_map() -> dict[str, str]:
    """Parse TENANT_ADMIN_KEYS_JSON: { "key_value": "tenant_id", ... }."""
    raw = getattr(settings, "TENANT_ADMIN_KEYS_JSON", None) or "{}"
    try:
        m = json.loads(raw)
        return {str(k): str(v) for k, v in (m or {}).items()}
    except Exception:
        return {}


def get_tenant_id_from_admin_key(x_admin_key: str | None) -> str | None:
    """Resolve tenant_id from x-admin-key only (no auth). For rate limit / logging. Returns None if invalid."""
    if not x_admin_key:
        return None
    key_map = _tenant_admin_keys_map()
    if key_map:
        return key_map.get(x_admin_key)
    if settings.ADMIN_API_KEY and x_admin_key == settings.ADMIN_API_KEY:
        return getattr(settings, "DEFAULT_TENANT_ID", None) or "default"
    return None


def require_admin_key(x_admin_key: str | None) -> dict[str, str]:
    """Validate x-admin-key; return user_id and tenant_id (for admin panel tenant scoping)."""
    if not x_admin_key:
        raise HTTPException(status_code=401, detail="unauthorized")

    key_map = _tenant_admin_keys_map()
    if key_map:
        tenant_id = key_map.get(x_admin_key)
        if tenant_id is not None:
            return {"user_id": "admin_api_key", "tenant_id": tenant_id}
        raise HTTPException(status_code=401, detail="unauthorized")

    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")
    default_tenant = getattr(settings, "DEFAULT_TENANT_ID", None) or "default"
    return {"user_id": "admin_api_key", "tenant_id": default_tenant}
