"""Tenant resolution for multi-dataset (Faz 1: public triage = single tenant; admin = key → tenant)."""

from __future__ import annotations

from app.core.config import settings


def get_default_tenant_id() -> str:
    """Tenant id for public triage (Faz 1: no X-Tenant-Id; always default)."""
    return settings.DEFAULT_TENANT_ID or "default"


def get_tenant_id_for_triage() -> str:
    """Alias for Faz 1: triage always uses default tenant."""
    return get_default_tenant_id()
