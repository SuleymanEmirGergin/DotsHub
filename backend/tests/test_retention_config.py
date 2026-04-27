"""Retention config defaults + env override smoke tests.

These guard the policy → code coupling described in
`docs/RETENTION_POLICY.md`: the privacy notice (compliance KR-2) cites
specific windows, and the SQL function in
`backend/sql/20260427_retention_purge.sql` defaults match these
constants. A silent change to either side would drift compliance.

We don't test the SQL function itself here — that needs a real
Postgres + the schema applied. Validation of those is via Supabase
staging dry-run (see RETENTION_POLICY.md option A pre-deploy step).
"""
from __future__ import annotations

import importlib

import pytest


def _reload_settings():
    """Pick up env mutations — Settings is instantiated at import time."""
    from app.core import config as config_module

    importlib.reload(config_module)
    return config_module.settings


def test_retention_default_windows():
    """Policy snapshot: the privacy notice promises these numbers."""
    from app.core.config import settings

    assert settings.RETENTION_DAYS_SESSIONS_TOMBSTONE == 90
    assert settings.RETENTION_DAYS_SESSIONS_PURGE == 90
    assert settings.RETENTION_DAYS_EVENTS == 90
    assert settings.RETENTION_DAYS_LLM_CALLS == 30
    assert settings.RETENTION_DAYS_FEEDBACK == 365
    assert settings.RETENTION_DAYS_PUSH_TOKENS == 90
    assert settings.RETENTION_DAYS_AUDIT == 730


def test_llm_calls_window_is_tightest():
    """High-PII surface (system prompt + symptom + LLM response) MUST
    have the shortest retention. If a future change makes this no
    longer true, compliance review is required."""
    from app.core.config import settings

    assert settings.RETENTION_DAYS_LLM_CALLS <= settings.RETENTION_DAYS_EVENTS
    assert settings.RETENTION_DAYS_LLM_CALLS <= settings.RETENTION_DAYS_SESSIONS_TOMBSTONE
    assert settings.RETENTION_DAYS_LLM_CALLS <= settings.RETENTION_DAYS_FEEDBACK


def test_purge_grace_at_least_one_week():
    """Tombstone-to-purge window must allow time for backup restore +
    user 'whoops, undo' contact path. Anything < 7 is suspicious."""
    from app.core.config import settings

    assert settings.RETENTION_DAYS_SESSIONS_PURGE >= 7


@pytest.mark.parametrize(
    "env_var,expected",
    [
        ("RETENTION_DAYS_SESSIONS_TOMBSTONE", 30),
        ("RETENTION_DAYS_LLM_CALLS", 7),
        ("RETENTION_DAYS_PUSH_TOKENS", 14),
    ],
)
def test_env_override_takes_precedence(monkeypatch, env_var, expected):
    """Dev environments shorten retention via env. Verify pydantic-settings
    actually picks the env up over the class default."""
    monkeypatch.setenv(env_var, str(expected))
    settings = _reload_settings()
    assert getattr(settings, env_var) == expected


def test_retention_audit_not_in_auto_purge():
    """Audit log retention (730 days) is documented as informational —
    `app_retention_purge()` SQL doesn't touch tenant_catalog_audit. If
    a future PR wires it in, the policy doc must be updated first."""
    sql_path = "backend/sql/20260427_retention_purge.sql"
    import os

    candidates = [sql_path, f"backend/{sql_path}", f"../{sql_path}"]
    for c in candidates:
        if os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                contents = f.read()
            assert "tenant_catalog_audit" not in contents.lower(), (
                "tenant_catalog_audit should not be in the auto-purge SQL "
                "without a corresponding policy update — see "
                "docs/RETENTION_POLICY.md"
            )
            return
    pytest.skip("retention SQL not found from this cwd")
