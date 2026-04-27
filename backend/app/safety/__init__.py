"""Safety package — emergency rule evaluation, single entry point.

Public API:
    from app.safety import check_safety, SafetyResult

Pipeline (short-circuit, deterministic-first — see ADR-001):

  1. Hard trigger (keyword → regex). Match → EMERGENCY, no LLM.
  2. Soft trigger + high-risk age. Combined match → EMERGENCY.
  3. Soft trigger alone (no high-risk age) → status=OK with
     `soft_triggers` populated; orchestrator drives follow-up
     questions.
  4. (Future, ADR-001 step 4) Optional LLM enrichment, opt-in via
     env flag. Intentionally not wired in this commit pending
     compliance C-3 (LLM provider DPA).

Hard guarantee: layers 1-2 are deterministic and LLM-bağımsız. If
the LLM (or any external) is down, hard rules still fire.

Both orchestrators (`triage_engine` and `agents/orchestrator`) should
call `check_safety` once per turn. The two old safety_guard modules
remain in place during migration — see ADR-001 action items 6, 7, 10.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.safety import deterministic, soft
from app.safety.types import SafetyPath, SafetyResult, SafetyStatus

__all__ = [
    "check_safety",
    "SafetyPath",
    "SafetyResult",
    "SafetyStatus",
]


def _record_path(path: SafetyPath) -> None:
    """Increment Prometheus counter; safe if metrics aren't installed."""
    try:
        from app.observability import safety_guard_triggers_total
    except ImportError:
        return
    if safety_guard_triggers_total is None:
        return
    safety_guard_triggers_total.labels(path=path).inc()


def check_safety(
    text_tr: str,
    answers: Optional[Dict[str, str]] = None,
    age: Optional[int] = None,
) -> SafetyResult:
    """Single safety entry point.

    Args:
        text_tr: User's free-text symptom description (Turkish).
        answers: Optional dict of question→answer pairs from the same
            turn. Hard triggers also scan answer values.
        age: Optional user age in years. Used for soft+age escalation.

    Returns a `SafetyResult`. `status="EMERGENCY"` ⇒ orchestrator must
    hard-stop and emit the EMERGENCY envelope. `status="OK"` may still
    carry `soft_triggers`; the orchestrator should propagate those into
    follow-up question selection.
    """
    hard = deterministic.evaluate(text_tr, answers)
    if hard is not None:
        _record_path(hard.path)
        return hard

    soft_match = soft.evaluate(text_tr, age)
    if soft_match is not None:
        _record_path(soft_match.path)
        return soft_match

    soft_only = soft.matched_soft_triggers(text_tr)
    if soft_only:
        result = SafetyResult(
            status="OK",
            soft_triggers=[str(t.get("id", "")) for t in soft_only],
            high_risk_age=False,
            path="none",
        )
        _record_path("none")
        return result

    _record_path("none")
    return SafetyResult(status="OK", path="none")
