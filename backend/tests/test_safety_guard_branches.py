"""Branch coverage for app.safety_guard.

Safety-critical module — target = 100% branch coverage.
Each test exercises one branch of `safety_guard_check`:
  - regex-match path
  - regex-compile failure fallback
  - keyword-match fallback path
  - answer-value aggregation path
  - no-match (returns None) path
"""
from __future__ import annotations

import pytest

from app.safety_guard import safety_guard_check


def _rules(triggers, default_instructions=None):
    payload = {"red_flags": {"hard_triggers": triggers}}
    if default_instructions is not None:
        payload["red_flags"]["emergency_instructions_tr"] = default_instructions
    return payload


# ─── Regex path ──────────────────────────────────────────────────────

def test_regex_match_triggers_emergency():
    rules = _rules([
        {
            "id": "ER_CHEST",
            "label": "Olası KAH",
            "regex": r"göğüs\s+ağrı",
        }
    ])
    out = safety_guard_check("hastada göğüs ağrısı başladı", {}, rules)
    assert out is not None
    assert out["rule_id"] == "ER_CHEST"
    assert out["reason_tr"] == "Olası KAH"
    # Default instructions come from the hard-coded fallback when the
    # rules file omits `emergency_instructions_tr`.
    assert out["instructions_tr"] == ["Derhal acil servise başvur veya 112'yi ara."]


def test_malformed_regex_falls_through_to_keyword():
    rules = _rules([
        {
            "id": "ER_KW",
            "label": "Keyword trigger",
            "regex": "[invalid(regex",  # re.error — swallowed (line 56-57)
            "keywords": ["bayılma"],
        }
    ])
    out = safety_guard_check("hasta bayılma geçirdi", {}, rules)
    assert out is not None
    assert out["rule_id"] == "ER_KW"


def test_regex_no_match_keyword_fallback_triggers():
    # regex present but doesn't hit; keyword fallback catches it.
    rules = _rules([
        {
            "id": "ER_KW2",
            "label": "kw fallback",
            "regex": r"koma",  # won't match
            "keywords": ["felç"],
        }
    ])
    out = safety_guard_check("ani gelişen felç tablosu", {}, rules)
    assert out is not None
    assert out["rule_id"] == "ER_KW2"


def test_keyword_only_trigger_no_regex_defined():
    # regex field absent — skips regex branch entirely (line 52 false)
    rules = _rules([
        {
            "id": "ER_KW3",
            "label": "kw only",
            "keywords": ["nefes darlığı"],
        }
    ])
    out = safety_guard_check("çok yoğun nefes darlığı", {}, rules)
    assert out is not None
    assert out["rule_id"] == "ER_KW3"


def test_empty_keyword_list_is_ignored():
    # kw_norm evaluates falsy when keyword is empty string (line 63)
    rules = _rules([
        {"id": "ER_EMPTY", "label": "x", "keywords": ["", "   "]}
    ])
    out = safety_guard_check("any text", {}, rules)
    assert out is None


def test_answers_values_aggregated_into_text():
    # User typed an emergency phrase as an *answer*, not in free text.
    rules = _rules([{"id": "ER_ANS", "label": "from answer", "keywords": ["bayılma"]}])
    out = safety_guard_check("yok bir şey", {"q1": "aslında bayılma yaşadım"}, rules)
    assert out is not None
    assert out["rule_id"] == "ER_ANS"


def test_answers_none_safe_fallback():
    # `(answers or {}).values()` handles None without raising.
    rules = _rules([{"id": "ER_X", "label": "x", "keywords": ["bayılma"]}])
    out = safety_guard_check("hafif baş ağrım", None, rules)  # type: ignore[arg-type]
    assert out is None


def test_no_trigger_returns_none():
    rules = _rules([{"id": "ER", "label": "x", "keywords": ["koma"]}])
    assert safety_guard_check("hafif baş ağrım var", {}, rules) is None


def test_empty_rules_returns_none():
    assert safety_guard_check("anything", {}, {"red_flags": {}}) is None
    assert safety_guard_check("anything", {}, {}) is None


def test_custom_emergency_instructions_used_when_provided():
    rules = _rules(
        [{"id": "ER", "label": "x", "keywords": ["koma"]}],
        default_instructions=["Custom TR instructions", "112"],
    )
    out = safety_guard_check("koma durumu", {}, rules)
    assert out is not None
    assert out["instructions_tr"] == ["Custom TR instructions", "112"]


def test_default_label_when_trigger_lacks_label():
    rules = _rules([{"id": "ER_NOLABEL", "keywords": ["bayılma"]}])
    out = safety_guard_check("bayılma", {}, rules)
    assert out is not None
    assert out["reason_tr"] == "Acil değerlendirme gerekebilir."
