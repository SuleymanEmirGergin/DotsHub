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


# ─── unittest setUp hook: cache cleanup ─────────────────────────────
#
# conftest.py has an autouse pytest fixture that clears in-memory
# rate-limit / idempotency / clinic-registry caches before every
# test. unittest discover doesn't fire pytest fixtures, so without
# this monkey-patch a unittest run accumulates rate-limit bucket
# state across tests and 429s fire in routes that should be 200.
#
# We hook into unittest.TestCase.setUp by wrapping the original (a
# no-op by default) so every TestCase in the suite picks this up
# without needing to inherit from a custom base class. Pytest also
# calls TestCase.setUp on classes derived from TestCase, so this
# duplicates the autouse fixture's work harmlessly under pytest.

import unittest as _unittest


def _clear_process_caches() -> None:
    try:
        from app import idempotency as _idem
        from app import rate_limit as _rl
        from app.services import clinic_registry as _cr
    except Exception:  # pragma: no cover — defensive (env not ready)
        return
    _idem._memory_clear()
    _rl._BUCKETS.clear()
    _rl._SESSION_BUCKETS.clear()
    _rl._SEND_SUMMARY_BUCKETS.clear()
    _rl._LLM_NLU_BUCKETS.clear()
    _rl._REDIS_DEGRADED_WARNED.clear()
    _cr.clear_cache()


_orig_setup = _unittest.TestCase.setUp


def _wrapped_setUp(self) -> None:
    _clear_process_caches()
    _orig_setup(self)


_unittest.TestCase.setUp = _wrapped_setUp  # type: ignore[assignment]
