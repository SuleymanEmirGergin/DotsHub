"""Backend pytest fixtures.

Two concerns solved here:

1. **Env stub** — `app/db.py` initialises the Supabase client at import
   time and raises if `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` are
   missing. Tests must never hit real Supabase, so we force stub values
   *before any test file is imported*. Using hard assignment (not
   `setdefault`) guarantees real `.env` contents cannot leak into a test
   run — env vars win over the `.env` file in Pydantic BaseSettings.

2. **Per-test runtime** — `load_runtime()` has no internal cache. The
   existing `setUpClass` pattern caches at class level which lets
   mutation bleed between tests in the same class. The `runtime`
   fixture below is function-scoped so every test reloads from disk.

Tests that need a specific env value should layer `monkeypatch.setenv`
on top of the stub baseline — overrides are clean because env > dotenv.
"""
from __future__ import annotations

import os

import pytest

# ─── Env stub ─────────────────────────────────────────────────────────
# Runs at conftest import time (pytest imports conftest.py files before
# any collected test module), so `app.db` — whenever it is imported
# transitively — sees stub values and never touches a real Supabase.

_STUB_ENV = {
    "SUPABASE_URL": "http://supabase.stub.local",
    "SUPABASE_SERVICE_ROLE_KEY": "stub-service-role-key",
    "SUPABASE_DB_URL": "postgresql://stub:stub@localhost/stub",
    "REDIS_URL": "",  # triggers in-memory fallback
    "IP_HASH_SALT": "test-salt",
    "ADMIN_API_KEY": "test-admin-key",
    "WIRO_API_KEY": "",
    "LLM_API_KEY": "",
    "LLM_NLU_ENABLED": "false",
    "FACILITY_DISCOVERY_ENABLED": "false",
    "WEBHOOK_ENABLED": "false",
}
for _k, _v in _STUB_ENV.items():
    os.environ[_k] = _v


@pytest.fixture
def runtime():
    """Fresh Runtime per test — no shared class-level state.

    Tests expected to be invoked with cwd=backend/ (pytest's rootdir
    with this pyproject.toml), so `data_dir="app/data"` resolves.
    """
    from app.runtime import load_runtime

    return load_runtime(data_dir="app/data")
