"""Shared admin authentication helpers."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.config import settings


def require_admin_key(x_admin_key: str | None) -> dict[str, str]:
    """Validate x-admin-key against ADMIN_API_KEY."""
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")

    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")

    return {"user_id": "admin_api_key"}
