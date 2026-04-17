#!/usr/bin/env python3
"""Shadow evaluation: deterministic NLU vs LLM NLU on golden flow scenarios.

Runs every scenario twice:

  Mode A — deterministic only      (LLM_NLU_ENABLED=False)
  Mode B — LLM NLU enabled         (LLM_NLU_ENABLED=True, real provider call)

Emits a per-scenario diff table and a JSON report.

Purpose
-------
The GoldenFlowsLLMABTests class in tests/test_golden_flows.py mocks
extract_canonicals_llm to return the deterministic canonicals, so it
only guards against structural regressions — it cannot tell us whether
the LLM actually *improves* routing quality. This script closes that
gap by calling the real LLM and scoring both modes against
scenario.expected.

Usage
-----
    # From the backend/ directory, with a real LLM provider configured:
    export WIRO_API_KEY=...            # or LLM_API_KEY for other providers
    python scripts/shadow_eval.py

    # Dry-run (no LLM key): shows what would be evaluated.
    python scripts/shadow_eval.py --dry-run

    # Write JSON report alongside console output:
    python scripts/shadow_eval.py --json-out shadow_eval_report.json

Exit codes
----------
    0  — evaluation completed (even if some scenarios disagree)
    1  — configuration error (no LLM key, bad arguments, etc.)
    2  — one or more scenarios crashed during evaluation

This is a *reporting* tool, not a gate. CI should not block on it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

# Ensure backend/ is on sys.path when invoked as `python scripts/shadow_eval.py`
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.runtime import load_runtime  # noqa: E402
from app.triage_engine import run_orchestrator_turn  # noqa: E402


SCENARIOS_DIR = _BACKEND_DIR.parent / "tests" / "golden_flows"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ModeResult:
    """Output of one orchestrator run for one scenario in one mode."""

    final_type: str
    specialty_id: Optional[str]
    confidence: float
    top_conditions: List[str]
    nlu_source: str
    elapsed_ms: int
    error: Optional[str] = None


@dataclass
class ScenarioComparison:
    scenario: str
    expected_type: Optional[str]
    expected_specialty: Optional[str]
    deterministic: ModeResult
    llm: ModeResult
    # Derived fields
    types_agree: bool = False
    specialties_agree: bool = False
    det_matches_expected_specialty: bool = False
    llm_matches_expected_specialty: bool = False
    confidence_delta: float = 0.0  # llm - det
    xfail_reason: Optional[str] = None


@dataclass
class Report:
    started_at: str
    total_scenarios: int
    scenarios_evaluated: int
    scenarios_crashed: int
    type_agreement_pct: float
    specialty_agreement_pct: float
    det_specialty_accuracy_pct: float
    llm_specialty_accuracy_pct: float
    llm_better_on: List[str] = field(default_factory=list)
    llm_worse_on: List[str] = field(default_factory=list)
    comparisons: List[ScenarioComparison] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def _run_scenario(runtime: Any, scenario: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Replay a scenario's turn list through the orchestrator.

    Mirrors the loop in tests/test_golden_flows.py so results are
    comparable to the golden flow test suite.
    """
    input_text = ""
    answers: Dict[str, str] = {}
    asked_canonicals: List[str] = []
    final_type = "ERROR"
    final_payload: Dict[str, Any] = {}

    for turn_index, step in enumerate(scenario.get("input", []), start=1):
        user_message = str(step.get("user_message") or "").strip()
        if user_message:
            input_text = (input_text + "\n" + user_message).strip()
        answer = step.get("answer")
        if isinstance(answer, dict):
            canonical = str(answer.get("canonical") or "").strip()
            value = str(answer.get("value") or "").strip()
            if canonical:
                answers[canonical] = value
                if canonical not in asked_canonicals:
                    asked_canonicals.append(canonical)

        final_type, final_payload, _ = run_orchestrator_turn(
            runtime=runtime,
            input_text=input_text,
            answers=answers,
            asked_canonicals=asked_canonicals,
            turn_index=turn_index,
        )
        if final_type in {"EMERGENCY", "ERROR"}:
            break

    return final_type, final_payload


def _to_mode_result(
    final_type: str,
    payload: Dict[str, Any],
    elapsed_ms: int,
    error: Optional[str] = None,
) -> ModeResult:
    specialty_id = (payload.get("recommended_specialty") or {}).get("id")
    top = [
        c.get("disease_label")
        for c in (payload.get("top_conditions") or [])
        if isinstance(c, dict) and c.get("disease_label")
    ]
    nlu_source = (payload.get("_meta") or {}).get("nlu_source", "?")
    return ModeResult(
        final_type=final_type,
        specialty_id=specialty_id,
        confidence=float(payload.get("confidence_0_1") or 0.0),
        top_conditions=top,
        nlu_source=nlu_source,
        elapsed_ms=elapsed_ms,
        error=error,
    )


def _run_with_llm_flag(
    runtime: Any, scenario: Dict[str, Any], llm_enabled: bool
) -> ModeResult:
    """Execute a scenario with LLM_NLU_ENABLED forced to the given value."""
    start = time.perf_counter()
    try:
        with patch("app.core.config.settings") as mock_s:
            # Preserve defaults we care about; override only the flag under test.
            from app.core.config import settings as real_settings

            mock_s.LLM_NLU_ENABLED = llm_enabled
            mock_s.MAX_QUESTIONS = getattr(real_settings, "MAX_QUESTIONS", 6)
            mock_s.LLM_PROVIDER = getattr(real_settings, "LLM_PROVIDER", "wiro")
            mock_s.LLM_NLU_MODEL = getattr(
                real_settings, "LLM_NLU_MODEL", "google/gemini-2-5-flash"
            )
            mock_s.LLM_NLU_TIMEOUT_SECONDS = getattr(
                real_settings, "LLM_NLU_TIMEOUT_SECONDS", 15.0
            )
            mock_s.LLM_NLU_POLL_INTERVAL_SECONDS = getattr(
                real_settings, "LLM_NLU_POLL_INTERVAL_SECONDS", 0.5
            )
            mock_s.LLM_NLU_LOG_TO_SUPABASE = False  # never log shadow eval to prod
            final_type, payload = _run_scenario(runtime, scenario)
    except Exception as exc:  # noqa: BLE001 — keep going across scenarios
        elapsed = int((time.perf_counter() - start) * 1000)
        return ModeResult(
            final_type="ERROR",
            specialty_id=None,
            confidence=0.0,
            top_conditions=[],
            nlu_source="?",
            elapsed_ms=elapsed,
            error=f"{type(exc).__name__}: {exc}",
        )
    elapsed = int((time.perf_counter() - start) * 1000)
    return _to_mode_result(final_type, payload, elapsed)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _compare(
    scenario_name: str, expected: Dict[str, Any], det: ModeResult, llm: ModeResult
) -> ScenarioComparison:
    expected_type = expected.get("final_type")
    expected_specialty = expected.get("recommended_specialty")

    types_agree = det.final_type == llm.final_type
    specialties_agree = det.specialty_id == llm.specialty_id
    det_match = bool(expected_specialty) and det.specialty_id == expected_specialty
    llm_match = bool(expected_specialty) and llm.specialty_id == expected_specialty

    return ScenarioComparison(
        scenario=scenario_name,
        expected_type=expected_type,
        expected_specialty=expected_specialty,
        deterministic=det,
        llm=llm,
        types_agree=types_agree,
        specialties_agree=specialties_agree,
        det_matches_expected_specialty=det_match,
        llm_matches_expected_specialty=llm_match,
        confidence_delta=round(llm.confidence - det.confidence, 4),
        xfail_reason=expected.get("xfail_reason"),
    )


def _print_table(comparisons: List[ScenarioComparison]) -> None:
    header = (
        f"{'Scenario':<42} {'exp spec':<14} "
        f"{'DET type':<9} {'DET spec':<14} {'DET conf':>8} "
        f"{'LLM type':<9} {'LLM spec':<14} {'LLM conf':>8} "
        f"{'d_conf':>7}  Verdict"
    )
    print("\n--- Shadow eval: deterministic vs LLM NLU ---")
    print(header)
    print("-" * len(header))
    for c in comparisons:
        verdict_parts = []
        if not c.types_agree:
            verdict_parts.append(f"type mismatch ({c.deterministic.final_type}->{c.llm.final_type})")
        if c.expected_specialty:
            if c.llm_matches_expected_specialty and not c.det_matches_expected_specialty:
                verdict_parts.append("LLM fixes routing")
            elif c.det_matches_expected_specialty and not c.llm_matches_expected_specialty:
                verdict_parts.append("LLM breaks routing")
        if c.deterministic.error or c.llm.error:
            verdict_parts.append("ERROR")
        if c.xfail_reason:
            verdict_parts.append("xfail")
        if not verdict_parts:
            verdict_parts.append("agree")
        print(
            f"{c.scenario:<42} {(c.expected_specialty or '-'):<14} "
            f"{c.deterministic.final_type:<9} {(c.deterministic.specialty_id or '-'):<14} "
            f"{c.deterministic.confidence:>8.3f} "
            f"{c.llm.final_type:<9} {(c.llm.specialty_id or '-'):<14} "
            f"{c.llm.confidence:>8.3f} "
            f"{c.confidence_delta:>+7.3f}  {', '.join(verdict_parts)}"
        )


def _summarize(comparisons: List[ScenarioComparison]) -> Report:
    total = len(comparisons)
    crashed = sum(
        1 for c in comparisons if c.deterministic.error or c.llm.error
    )
    evaluated = total - crashed

    type_agree = sum(1 for c in comparisons if c.types_agree)
    spec_agree = sum(1 for c in comparisons if c.specialties_agree)
    scenarios_with_expected_spec = [c for c in comparisons if c.expected_specialty]
    det_correct = sum(
        1 for c in scenarios_with_expected_spec if c.det_matches_expected_specialty
    )
    llm_correct = sum(
        1 for c in scenarios_with_expected_spec if c.llm_matches_expected_specialty
    )

    llm_better = [
        c.scenario
        for c in scenarios_with_expected_spec
        if c.llm_matches_expected_specialty and not c.det_matches_expected_specialty
    ]
    llm_worse = [
        c.scenario
        for c in scenarios_with_expected_spec
        if c.det_matches_expected_specialty and not c.llm_matches_expected_specialty
    ]

    def _pct(num: int, denom: int) -> float:
        return round(100.0 * num / denom, 2) if denom else 0.0

    return Report(
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S"),
        total_scenarios=total,
        scenarios_evaluated=evaluated,
        scenarios_crashed=crashed,
        type_agreement_pct=_pct(type_agree, total),
        specialty_agreement_pct=_pct(spec_agree, total),
        det_specialty_accuracy_pct=_pct(det_correct, len(scenarios_with_expected_spec)),
        llm_specialty_accuracy_pct=_pct(llm_correct, len(scenarios_with_expected_spec)),
        llm_better_on=llm_better,
        llm_worse_on=llm_worse,
        comparisons=comparisons,
    )


def _print_summary(report: Report) -> None:
    print("\n--- Summary ---")
    print(f"  Scenarios evaluated : {report.scenarios_evaluated}/{report.total_scenarios}")
    if report.scenarios_crashed:
        print(f"  Scenarios crashed   : {report.scenarios_crashed}")
    print(f"  final_type agreement: {report.type_agreement_pct}%")
    print(f"  specialty agreement : {report.specialty_agreement_pct}%")
    print(f"  DET specialty acc.  : {report.det_specialty_accuracy_pct}%")
    print(f"  LLM specialty acc.  : {report.llm_specialty_accuracy_pct}%")
    if report.llm_better_on:
        print(f"  LLM fixes routing on: {', '.join(report.llm_better_on)}")
    if report.llm_worse_on:
        print(f"  LLM breaks routing  : {', '.join(report.llm_worse_on)}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def _have_llm_credentials() -> bool:
    """Return True if some plausible LLM credential is visible in env."""
    candidates = (
        "WIRO_API_KEY",
        "LLM_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    )
    return any(os.environ.get(k) for k in candidates)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List scenarios that would be evaluated without calling the LLM.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write a JSON report to this path in addition to console output.",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=SCENARIOS_DIR,
        help="Override the golden_flows directory (default: tests/golden_flows).",
    )
    args = parser.parse_args(argv)

    scenarios_dir: Path = args.scenarios_dir
    scenario_files = sorted(scenarios_dir.glob("*.json"))
    if not scenario_files:
        print(f"ERROR: no scenario files found in {scenarios_dir}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"[dry-run] {len(scenario_files)} scenarios would be evaluated:")
        for p in scenario_files:
            print(f"  - {p.name}")
        print("\n[dry-run] No LLM calls issued. Set WIRO_API_KEY (or LLM_API_KEY) and")
        print("[dry-run] re-run without --dry-run to collect a real comparison.")
        return 0

    if not _have_llm_credentials():
        print(
            "ERROR: no LLM credentials found in env. Set one of: "
            "WIRO_API_KEY, LLM_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY.\n"
            "Or invoke with --dry-run to preview the scenario list without calling the LLM.",
            file=sys.stderr,
        )
        return 1

    print(f"Loading runtime from {(_BACKEND_DIR / 'app' / 'data').resolve()} ...")
    runtime = load_runtime(data_dir=str(_BACKEND_DIR / "app" / "data"))

    comparisons: List[ScenarioComparison] = []
    for scenario_path in scenario_files:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        expected = scenario.get("expected", {})

        print(f"  -> {scenario_path.name} ... ", end="", flush=True)
        det = _run_with_llm_flag(runtime, scenario, llm_enabled=False)
        llm = _run_with_llm_flag(runtime, scenario, llm_enabled=True)
        comparisons.append(_compare(scenario_path.name, expected, det, llm))
        verdict = "ok"
        if det.error or llm.error:
            verdict = f"ERROR (det={det.error} llm={llm.error})"
        print(f"{verdict} (det={det.elapsed_ms}ms, llm={llm.elapsed_ms}ms)")

    _print_table(comparisons)
    report = _summarize(comparisons)
    _print_summary(report)

    if args.json_out:
        # Convert nested dataclasses to dicts for JSON serialization.
        payload = asdict(report)
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")

    return 2 if report.scenarios_crashed else 0


if __name__ == "__main__":
    raise SystemExit(main())
