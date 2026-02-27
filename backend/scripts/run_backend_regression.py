#!/usr/bin/env python3
"""Run backend regression checks with CI parity."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]


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
]


def main() -> int:
    completed = 0

    for step in STEPS:
        print(f"[run_backend_regression] START {step.name}: {' '.join(step.command)}", flush=True)
        result = subprocess.run(step.command, check=False)
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
