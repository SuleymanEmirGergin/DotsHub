"""Backend pytest fixtures.

**Env stub moved to `tests/__init__.py`** — the stub must run under
both pytest AND `python -m unittest discover` (used by CI via
`scripts/run_backend_regression.py`), and conftest.py is a pytest-only
convention. See the docstring in `__init__.py` for the rationale.

What remains here:

- **Per-test runtime** — `load_runtime()` has no internal cache. The
  existing `setUpClass` pattern caches at class level which lets
  mutation bleed between tests in the same class. The `runtime`
  fixture below is function-scoped so every test reloads from disk.

Tests that need a specific env value should layer `monkeypatch.setenv`
on top of the stub baseline from `__init__.py` — overrides are clean
because env > dotenv.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def runtime():
    """Fresh Runtime per test — no shared class-level state.

    Tests expected to be invoked with cwd=backend/ (pytest's rootdir
    with this pyproject.toml), so `data_dir="app/data"` resolves.
    """
    from app.runtime import load_runtime

    return load_runtime(data_dir="app/data")
