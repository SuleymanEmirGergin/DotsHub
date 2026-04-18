#!/usr/bin/env python3
"""Coverage gate for safety-critical hot-path modules.

What this guards: if a future change rips out a test or a branch without
replacing it, the coverage% on the listed modules will drop and CI will
fail here — surfacing the regression before it lands on main.

What this is NOT: a repo-wide coverage gate. We deliberately don't
require coverage on modules that are still in-flight, externally mocked,
or primarily exercised via integration. The list below is the set whose
correctness is load-bearing for triage output, plus the observability
modules that carry incident-response paths.

Thresholds are per-module rather than a single global number — a 90%
total can hide a 40% on a critical module. Bump a threshold only when
the module's actual coverage is clearly and durably above the new
value; drop one only with a written reason.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# module path → minimum coverage percentage
THRESHOLDS: dict[str, float] = {
    "app/canonical_extract.py": 100.0,
    "app/emergency_router.py": 100.0,
    "app/top_conditions_filter.py": 100.0,
    "app/triage_engine.py": 85.0,
    "app/services/llm_nlu.py": 75.0,
}


def _run_coverage() -> int:
    """Run the test suite under coverage, collect into .coverage."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--source=app",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
            "-q",
        ],
        check=False,
    ).returncode


def _load_coverage():
    import coverage

    c = coverage.Coverage()
    c.load()
    return c


def main() -> int:
    rc = _run_coverage()
    if rc != 0:
        print(
            "[check_hotpath_coverage] tests failed — see output above; "
            "coverage gate skipped.",
            file=sys.stderr,
        )
        return rc

    try:
        c = _load_coverage()
    except Exception as exc:  # noqa: BLE001
        print(f"[check_hotpath_coverage] could not load .coverage: {exc}", file=sys.stderr)
        return 2

    failures: list[tuple[str, float, float]] = []
    worktree_root = Path(__file__).resolve().parents[1]

    for rel_path, min_pct in THRESHOLDS.items():
        abs_path = worktree_root / rel_path
        try:
            _, statements, _excluded, missing, _ = c.analysis2(str(abs_path))
        except Exception as exc:  # noqa: BLE001
            print(
                f"[check_hotpath_coverage] {rel_path}: could not analyze ({exc})",
                file=sys.stderr,
            )
            failures.append((rel_path, 0.0, min_pct))
            continue

        stmt_count = len(statements)
        miss_count = len(missing)
        if stmt_count == 0:
            pct = 100.0
        else:
            pct = 100.0 * (stmt_count - miss_count) / stmt_count

        marker = "OK" if pct >= min_pct else "FAIL"
        print(
            f"[check_hotpath_coverage] {marker:<4} {rel_path:<40} "
            f"{pct:6.2f}% (min {min_pct:.0f}%) — {miss_count}/{stmt_count} lines missed"
        )
        if pct < min_pct:
            failures.append((rel_path, pct, min_pct))

    if failures:
        print("", file=sys.stderr)
        print(
            f"[check_hotpath_coverage] {len(failures)} module(s) below threshold:",
            file=sys.stderr,
        )
        for path, got, need in failures:
            print(f"  - {path}: {got:.2f}% < {need:.0f}%", file=sys.stderr)
        return 1

    print(
        f"[check_hotpath_coverage] all {len(THRESHOLDS)} hot-path modules "
        "meet their coverage floor.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
