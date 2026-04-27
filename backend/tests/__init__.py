"""Test package init.

The conftest.py file in this directory sets the same env stubs for
pytest, but `python -m unittest discover` does NOT load conftest.py
— it only loads regular Python packages. This `__init__.py` runs at
package-import time (which both pytest and unittest do) and sets the
stub env BEFORE any test module attempts ``from app.main import app``.

Without this file, unittest discover hits ``app/db.py``'s import-time
``RuntimeError("Missing SUPABASE_URL...")`` for every test that
transitively imports the FastAPI app, which is most of them.

Pytest readers: this file is harmless to you — conftest.py runs
afterwards and re-sets the same values (idempotent), and the
autouse fixtures it defines still apply.
"""
from __future__ import annotations

import os

# Mirror the _STUB_ENV in conftest.py. Setting via os.environ (NOT
# setdefault) so a misconfigured CI runner that exports a real
# Supabase URL into the test job is overridden — tests must NEVER
# accidentally hit a real Supabase.
_STUB_ENV = {
    "SUPABASE_URL": "http://supabase.stub.local",
    "SUPABASE_SERVICE_ROLE_KEY": "stub-service-role-key",
    "SUPABASE_DB_URL": "postgresql://stub:stub@localhost/stub",
    "REDIS_URL": "",  # triggers in-memory fallback
    "IP_HASH_SALT": "test-salt",
    "ADMIN_API_KEY": "test-admin-key",
    "WIRO_API_KEY": "",
    "WIRO_API_SECRET": "stub-wiro-secret",
    "LLM_API_KEY": "",
    "LLM_NLU_ENABLED": "false",
    "FACILITY_DISCOVERY_ENABLED": "false",
    "WEBHOOK_ENABLED": "false",
}
for _k, _v in _STUB_ENV.items():
    os.environ[_k] = _v
