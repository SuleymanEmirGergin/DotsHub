"""Tests for the consolidated `app.safety` package (ADR-001).

Uses the real `app/data/rules.json` so any drift in trigger definitions
is caught here, not in production. Triggers referenced below are
verified to exist at the time these tests were written:

- `breathing_severe` hard trigger has keyword "boğuluyorum" and a regex
  that also matches "boğuluycam" (which is NOT in the keyword list —
  good for distinguishing keyword vs. regex paths).
- `fever_neck_stiffness` soft trigger has keyword "yüksek ateş".
- `age_risk_adjustment.high_risk_ages` covers 0-5 (min/max) and
  65-120 (min2/max2).

The package under test is dormant in production until the orchestrator
call sites migrate (see ADR-001 action items 6, 7). These tests
confirm the package is ready to be wired in.
"""
from __future__ import annotations

import pytest

from app.safety import check_safety
from app.safety.types import SafetyResult


# ─── Hard trigger paths ─────────────────────────────────────────────


def test_hard_keyword_match_emergency():
    """Plain keyword substring → EMERGENCY via the keyword path."""
    result = check_safety("Sürekli boğuluyorum, nefes alamıyorum")
    assert result.status == "EMERGENCY"
    assert result.rule_id == "breathing_severe"
    assert result.path == "hard_keyword"
    assert result.instructions_tr  # Non-empty fallback list at minimum
    assert result.high_risk_age is False


def test_hard_keyword_uppercase_turkish_normalized():
    """Turkish-aware lowercase: capital İ/I should still match keywords.

    The old agent path used plain `.lower()` which corrupts İ→i+̇.
    The consolidation uses `normalize_text_tr` which handles this.
    """
    result = check_safety("BOĞULUYORUM")
    assert result.status == "EMERGENCY"
    assert result.path == "hard_keyword"


def test_hard_regex_match_when_keyword_does_not():
    """Regex covers variants the keyword list doesn't enumerate.

    "boğuluycam" matches the breathing_severe regex but is not in
    the keyword list, so we hit the regex path specifically.
    """
    result = check_safety("yardım edin boğuluycam")
    assert result.status == "EMERGENCY"
    assert result.rule_id == "breathing_severe"
    assert result.path == "hard_regex"


def test_hard_trigger_via_answers_field():
    """Hard triggers also scan answer values, not just primary text.

    The old top-level safety_guard searched answers; the agent path
    did not. The consolidation always searches both — closes the gap.
    """
    result = check_safety("normal bir gun", answers={"q1": "boğuluyorum"})
    assert result.status == "EMERGENCY"
    assert result.path == "hard_keyword"


# ─── Soft trigger + age paths ───────────────────────────────────────


def test_soft_alone_low_risk_age_returns_ok_with_soft_triggers():
    """Soft trigger without high-risk age → OK but soft_triggers populated.

    Orchestrator uses this to drive follow-up question selection.
    """
    result = check_safety("birkaç gündür yüksek ateş var", age=30)
    assert result.status == "OK"
    assert "fever_neck_stiffness" in result.soft_triggers
    assert result.high_risk_age is False
    assert result.path == "none"


def test_soft_alone_no_age_returns_ok_with_soft_triggers():
    """age=None is treated as not-high-risk."""
    result = check_safety("yüksek ateş", age=None)
    assert result.status == "OK"
    assert "fever_neck_stiffness" in result.soft_triggers
    assert result.high_risk_age is False


@pytest.mark.parametrize("age", [0, 3, 5, 65, 80, 120])
def test_soft_plus_high_risk_age_escalates_to_emergency(age):
    """Soft trigger + age in either high-risk band → EMERGENCY."""
    result = check_safety("yüksek ateş şikayetim var", age=age)
    assert result.status == "EMERGENCY"
    assert result.path == "soft_age"
    assert result.high_risk_age is True
    assert "fever_neck_stiffness" in result.soft_triggers
    assert str(age) in result.reason_tr


@pytest.mark.parametrize("age", [6, 30, 64])
def test_soft_with_mid_age_does_not_escalate(age):
    """Ages outside both high-risk bands stay OK."""
    result = check_safety("yüksek ateş", age=age)
    assert result.status == "OK"
    assert result.high_risk_age is False


# ─── No-trigger paths ───────────────────────────────────────────────


def test_no_trigger_returns_ok():
    result = check_safety("biraz başım ağrıyor, çok önemli değil")
    assert result.status == "OK"
    assert result.path == "none"
    assert result.soft_triggers == []
    assert result.rule_id is None


def test_empty_text_returns_ok():
    result = check_safety("")
    assert result.status == "OK"
    assert result.path == "none"


def test_empty_text_with_empty_answers():
    result = check_safety("", answers={})
    assert result.status == "OK"


# ─── Hard trigger short-circuits soft ──────────────────────────────


def test_hard_trigger_wins_over_soft_and_age():
    """Even with high-risk age and soft keyword present, hard trigger
    fires first and returns its own path label."""
    result = check_safety(
        "yüksek ateş ve boğuluyorum",
        age=80,
    )
    assert result.status == "EMERGENCY"
    # Hard path wins — not soft_age
    assert result.path in ("hard_keyword", "hard_regex")
    assert result.rule_id == "breathing_severe"


# ─── Result shape contract ──────────────────────────────────────────


def test_result_is_frozen_dataclass():
    """SafetyResult is frozen — orchestrators can't mutate after return."""
    result = check_safety("normal")
    with pytest.raises((AttributeError, TypeError)):
        result.status = "EMERGENCY"  # type: ignore[misc]


def test_result_default_lists_are_independent():
    """Two SafetyResults with default lists shouldn't share state."""
    a = SafetyResult(status="OK")
    b = SafetyResult(status="OK")
    assert a.instructions_tr is not b.instructions_tr
    assert a.soft_triggers is not b.soft_triggers


# ─── Metric wiring smoke test ──────────────────────────────────────


def test_metric_increments_on_each_check():
    """The `safety_guard_triggers_total` counter increments by `path`.

    We don't assert exact values (other tests in the suite touch the
    same counter); we just confirm the counter exists, has the right
    label, and accepts increments without error.
    """
    from app.observability import safety_guard_triggers_total

    before = safety_guard_triggers_total.labels(path="hard_keyword")._value.get()
    check_safety("boğuluyorum")
    after = safety_guard_triggers_total.labels(path="hard_keyword")._value.get()
    assert after == before + 1
