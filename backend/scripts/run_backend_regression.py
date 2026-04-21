#!/usr/bin/env python3
"""Run backend regression checks with CI parity."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    env_override: dict[str, str] | None = None


# Baseline env stub applied to every step.
#
# `app/db.py` initialises the Supabase client at module import time and
# raises RuntimeError if SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are
# missing. The test-package `tests/__init__.py` stubs the same vars so
# pytest and `python -m unittest tests.foo` work without a real
# Supabase. But `unittest discover -s tests -p test_*.py` treats each
# test file as a top-level module and does NOT import the parent
# package, so `__init__.py` never runs — and step 2 here was failing
# with "Missing SUPABASE_URL". Setting stubs at the script level
# guarantees CI has the same baseline regardless of discovery mode.
#
# Hard-assign (not setdefault) so a stale real .env in the CI runner
# can't leak into a test run.
_STUB_ENV = {
    "SUPABASE_URL": "http://supabase.stub.local",
    "SUPABASE_SERVICE_ROLE_KEY": "stub-service-role-key",
    "SUPABASE_DB_URL": "postgresql://stub:stub@localhost/stub",
    "REDIS_URL": "",  # triggers in-memory fallback for rate limits
    "IP_HASH_SALT": "test-salt",
    "ADMIN_API_KEY": "test-admin-key",
    "WIRO_API_KEY": "",
    "LLM_API_KEY": "",
    "LLM_NLU_ENABLED": "false",
    "FACILITY_DISCOVERY_ENABLED": "false",
    "WEBHOOK_ENABLED": "false",
}


STEPS = [
    Step(
        name="golden_flow_regression",
        command=[sys.executable, "-m", "unittest", "tests.test_golden_flows", "-v"],
    ),
    Step(
        name="backend_test_suite",
        command=[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-q"],
    ),
    Step(
        name="kaggle_mapping_guardrails",
        command=[sys.executable, "scripts/validate_kaggle_mapping.py"],
    ),
    # Hot-path coverage gate — runs the test suite a second time under
    # coverage and asserts per-module minimums (see the script for the
    # threshold rationale). Kept as a separate step so the first suite
    # fails fast on a real test regression without waiting for the
    # coverage measurement.
    Step(
        name="hotpath_coverage_gate",
        command=[sys.executable, "scripts/check_hotpath_coverage.py"],
    ),
]


def _env_for_step(step: Step) -> dict[str, str]:
    env = os.environ.copy()
    env.update(_STUB_ENV)
    if step.env_override:
        env.update(step.env_override)
    return env


def main() -> int:
    completed = 0

    for step in STEPS:
        print(f"[run_backend_regression] START {step.name}: {' '.join(step.command)}", flush=True)
        result = subprocess.run(step.command, check=False, env=_env_for_step(step))
        if result.returncode != 0:
            print(
                f"BACKEND_REGRESSION_SUMMARY status=FAIL failed_step={step.name} completed={completed}/{len(STEPS)}",
                flush=True,
            )
            return result.returncode
        completed += 1

    print(f"BACKEND_REGRESSION_SUMMARY status=PASS completed={completed}/{len(STEPS)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
