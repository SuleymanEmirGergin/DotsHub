"""Test-package initialiser — **env stub for any test runner**.

Why this lives here and not in `conftest.py`:

    `conftest.py` is a pytest-only convention. Our CI runs the backend
    suite through `python -m unittest discover` (see
    `scripts/run_backend_regression.py`), which does not execute
    conftest files. The env stub must therefore run from a location
    both runners will hit.

    A test-package `__init__.py` is imported by unittest's loader
    before any `tests.test_*` module, and pytest also imports it when
    rootdir + testpaths resolve. Putting the stub here guarantees
    coverage across both entrypoints.

The two concerns:

1. **Env stub** — `app/db.py` initialises the Supabase client at
   import time and raises if `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`
   are missing. Tests must never hit real Supabase, so we force stub
   values *before any test file is imported*. Using hard assignment
   (not `setdefault`) guarantees real `.env` contents cannot leak into
   a test run — env vars win over the `.env` file in Pydantic
   BaseSettings.

2. **Per-test runtime** — see `conftest.py` for the pytest `runtime`
   fixture. That part remains in conftest because it's a fixture,
   not a module-level side-effect.

Tests that need a specific env value should layer `monkeypatch.setenv`
(pytest) or `unittest.mock.patch.dict(os.environ, ...)` on top of this
baseline — overrides are clean because env > dotenv.
"""
from __future__ import annotations

import os

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
