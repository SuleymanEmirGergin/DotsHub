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


STEPS = [
    Step(
        name="golden_flow_regression",
        command=[sys.executable, "-m", "unittest", "tests.test_golden_flows", "-v"],
    ),
    Step(
        # pytest used to run via `unittest discover` here, but pytest-
        # only fixtures (autouse cache cleanup in tests/conftest.py,
        # monkeypatch in pytest-style function tests) only fire when
        # pytest is the runner. unittest discover left rate-limit
        # buckets bleeding across tests and skipped pytest-style
        # tests entirely. Pytest auto-collects unittest.TestCase
        # subclasses too, so this is a strict superset of the old
        # behaviour with the fixtures actually firing.
        name="backend_test_suite",
        command=[
            sys.executable, "-m", "pytest",
            "tests/",
            "-q",
            "--ignore=tests/test_benchmarks.py",  # benchmark suite is a separate gate
            "-p", "no:cacheprovider",
        ],
        env_override={"REDIS_URL": ""},
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
        env_override={"REDIS_URL": ""},
    ),
]


def _env_for_step(step: Step) -> dict[str, str]:
    env = os.environ.copy()
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
