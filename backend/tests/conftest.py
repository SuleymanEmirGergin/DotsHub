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
    # Stub secret so app.services.ai.wiro_client.require_signature_auth()
    # accepts test calls. Tests that explicitly want the unset path
    # (test_ai_wiro_client.test_submit_raises_when_signature_unset)
    # use monkeypatch.delenv() to override.
    "WIRO_API_SECRET": "stub-wiro-secret",
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


# ─── Process-state cleanup between tests ─────────────────────────────
#
# Several modules keep mutable in-memory caches at the module level:
#   - app.rate_limit._BUCKETS / _SESSION_BUCKETS / _SEND_SUMMARY_BUCKETS /
#     _LLM_NLU_BUCKETS — rate-limit deques per ip / device / session.
#   - app.idempotency._MEMORY_CACHE — request-replay LRU.
#   - app.services.clinic_registry._JSON_CACHE / _SUPABASE_CACHE — clinic
#     registry; Supabase fixtures must not bleed into the next test.
#
# Without a teardown, IP "127.0.0.1" fills its bucket within a few
# tests and every later TestClient call to /v1/triage/* or /v1/quote*
# trips a 429 — masking the actual behaviour the test was asserting.
# Eight test files used to repeat this cleanup in setUp/tearDown; now
# it lives in one autouse fixture so future tests get it for free.

@pytest.fixture(autouse=True)
def _reset_process_caches():
    """Wipe rate-limit, idempotency, and registry caches before each
    test. Imports are local so `conftest.py` import doesn't pull the
    full app graph (some unit-test runs deliberately use a narrow
    subset of modules)."""
    try:
        from app import idempotency as _idem
        from app import rate_limit as _rl
        from app.services import clinic_registry as _cr
    except Exception:  # pragma: no cover — defensive
        yield
        return

    def _clear() -> None:
        _idem._memory_clear()
        _rl._BUCKETS.clear()
        _rl._SESSION_BUCKETS.clear()
        _rl._SEND_SUMMARY_BUCKETS.clear()
        _rl._LLM_NLU_BUCKETS.clear()
        # Dedup-warn set: one warning per process per bucket key. Tests
        # that exercise the Redis-degraded path expect a fresh slate.
        _rl._REDIS_DEGRADED_WARNED.clear()
        _cr.clear_cache()

    _clear()
    yield
    _clear()
