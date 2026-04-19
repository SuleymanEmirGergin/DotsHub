"""Branch coverage for app.emergency_router.

Safety-critical module — target = 100% branch coverage. Pure functions,
no I/O except `load_emergency_rules`. Tests are pytest-style (no
unittest.TestCase) to demonstrate the conftest-based pattern.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.emergency_router import (
    EmergencyMatch,
    canon_any,
    contains_all,
    contains_any,
    evaluate_emergency,
    group_match,
    load_emergency_rules,
    norm_list,
    norm_text_tr,
)


# ─── norm_text_tr ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),  # falsy string
        (None, ""),  # None → "" via `(s or "")`
        ("  Merhaba!  ", "merhaba"),  # strip + lower + punctuation stripped
        ("Göğüs ağrısı, çok şiddetli.", "göğüs ağrısı çok şiddetli"),  # TR chars kept
        ("line1\n\nline2", "line1 line2"),  # whitespace collapse
    ],
)
def test_norm_text_tr_edges(raw, expected):
    assert norm_text_tr(raw) == expected


# ─── norm_list ───────────────────────────────────────────────────────

def test_norm_list_filters_empty_and_returns_set():
    got = norm_list(["Ateş", "", "  ", "başağrısı", "başağrısı"])
    # empty strings filtered; duplicates collapsed by set semantics
    assert got == {"ateş", "başağrısı"}


def test_norm_list_none_input():
    assert norm_list(None) == set()  # `(items or [])` path


# ─── contains_any / contains_all ─────────────────────────────────────

def test_contains_any_no_phrases_returns_false():
    assert contains_any("anything", []) is False
    assert contains_any("anything", None) is False


def test_contains_any_hit_on_first_match():
    assert contains_any("şiddetli göğüs ağrısı", ["bayılma", "göğüs ağrısı"]) is True


def test_contains_any_no_match_returns_false():
    assert contains_any("hafif karın ağrısı", ["göğüs ağrısı", "nefes darlığı"]) is False


def test_contains_any_empty_phrase_skipped():
    # `if pn and pn in t` — empty normalized phrase should not cause True
    assert contains_any("anything", ["", "  "]) is False


def test_contains_all_no_phrases_returns_false():
    assert contains_all("anything", []) is False
    assert contains_all("anything", None) is False


def test_contains_all_every_phrase_present():
    assert contains_all("göğüs ağrısı ve nefes darlığı", ["göğüs ağrısı", "nefes darlığı"]) is True


def test_contains_all_one_missing_returns_false():
    assert contains_all("sadece göğüs ağrısı", ["göğüs ağrısı", "nefes darlığı"]) is False


def test_contains_all_empty_phrase_skipped_still_passes():
    # `if pn and pn not in t` — empty normalized phrase is skipped, real ones must match
    assert contains_all("göğüs ağrısı", ["", "göğüs ağrısı"]) is True


# ─── canon_any ───────────────────────────────────────────────────────

def test_canon_any_no_wanted_returns_false():
    assert canon_any({"ateş"}, []) is False


def test_canon_any_intersection_hit():
    assert canon_any({"ateş", "öksürük"}, ["Ateş"]) is True  # case-insensitive via norm


def test_canon_any_no_overlap():
    assert canon_any({"ateş"}, ["öksürük"]) is False


# ─── group_match ─────────────────────────────────────────────────────

def test_group_match_keyword_any_branch():
    g = {"keyword_any": ["kusma"]}
    assert group_match("bulantı ve kusma", set(), g) is True


def test_group_match_keyword_all_branch():
    g = {"keyword_all": ["ateş", "halsizlik"]}
    assert group_match("yüksek ateş ve halsizlik", set(), g) is True


def test_group_match_canonical_any_branch():
    g = {"canonical_any": ["ateş"]}
    assert group_match("any text", {"ateş"}, g) is True


def test_group_match_nothing_matches_returns_false():
    g = {"keyword_any": ["koma"], "keyword_all": ["x", "y"], "canonical_any": ["z"]}
    assert group_match("hafif ağrı", {"başka"}, g) is False


def test_group_match_empty_group_returns_false():
    assert group_match("text", set(), {}) is False


# ─── load_emergency_rules ────────────────────────────────────────────

def test_load_emergency_rules_roundtrip(tmp_path):
    p = tmp_path / "rules.json"
    payload = {"rules": [{"id": "r1", "severity": 3}], "global": {"min_severity_to_trigger": 2}}
    p.write_text(json.dumps(payload), encoding="utf-8")

    got = load_emergency_rules(str(p))

    assert got == payload


# ─── evaluate_emergency ──────────────────────────────────────────────

def _rules(rules, min_sev=2):
    return {"global": {"min_severity_to_trigger": min_sev}, "rules": rules}


def test_evaluate_emergency_severity_below_threshold_skipped():
    cfg = _rules([{"id": "r1", "severity": 1, "keyword_any": ["bayılma"]}], min_sev=2)
    assert evaluate_emergency(user_text="bayılma", canonicals_tr=[], rules_cfg=cfg) is None


def test_evaluate_emergency_keyword_all_hit():
    cfg = _rules([
        {
            "id": "r_all",
            "severity": 3,
            "keyword_all": ["göğüs ağrısı", "kola yayılım"],
            "title_tr": "KAH şüphesi",
            "message_tr": "msg",
            "recommendation_tr": "112",
        }
    ])
    m = evaluate_emergency(
        user_text="göğüs ağrısı ve sol kola yayılım var",
        canonicals_tr=[],
        rules_cfg=cfg,
    )
    assert isinstance(m, EmergencyMatch)
    assert m.rule_id == "r_all"
    assert m.matched_on["reasons"] == {"keyword_all": ["göğüs ağrısı", "kola yayılım"]}


def test_evaluate_emergency_keyword_any_hit_when_all_misses():
    cfg = _rules([
        {
            "id": "r_any",
            "severity": 3,
            "keyword_all": ["x", "y"],  # won't match
            "keyword_any": ["bayılma"],
            "title_tr": "t",
            "message_tr": "m",
            "recommendation_tr": "112",
        }
    ])
    m = evaluate_emergency(user_text="bayılma oldu", canonicals_tr=[], rules_cfg=cfg)
    assert m is not None and "keyword_any" in m.matched_on["reasons"]


def test_evaluate_emergency_canonical_any_hit_when_keywords_miss():
    cfg = _rules([
        {
            "id": "r_canon",
            "severity": 3,
            "canonical_any": ["koma"],
            "title_tr": "t",
            "message_tr": "m",
            "recommendation_tr": "112",
        }
    ])
    m = evaluate_emergency(user_text="hiçbir şey", canonicals_tr=["koma"], rules_cfg=cfg)
    assert m is not None and "canonical_any" in m.matched_on["reasons"]


def test_evaluate_emergency_require_group_gate_confirms_hit():
    cfg = _rules([
        {
            "id": "r_gate",
            "severity": 3,
            "keyword_any": ["bayılma"],
            "require_any_group": [{"keyword_any": ["nefes darlığı"]}],
            "title_tr": "t",
            "message_tr": "m",
            "recommendation_tr": "112",
        }
    ])
    m = evaluate_emergency(
        user_text="bayılma ve nefes darlığı",
        canonicals_tr=[],
        rules_cfg=cfg,
    )
    assert m is not None and "require_any_group" in m.matched_on["reasons"]


def test_evaluate_emergency_require_group_gate_reverts_hit():
    cfg = _rules([
        {
            "id": "r_gate_fail",
            "severity": 3,
            "keyword_any": ["bayılma"],
            "require_any_group": [{"keyword_any": ["nefes darlığı"]}],
            "title_tr": "t",
            "message_tr": "m",
            "recommendation_tr": "112",
        }
    ])
    # keyword_any hits "bayılma" but require_any_group fails → no match
    assert evaluate_emergency(user_text="bayılma var", canonicals_tr=[], rules_cfg=cfg) is None


def test_evaluate_emergency_no_match_returns_none():
    cfg = _rules([
        {"id": "r", "severity": 3, "keyword_any": ["koma"], "title_tr": "t", "message_tr": "m"}
    ])
    assert evaluate_emergency(user_text="hafif başağrısı", canonicals_tr=[], rules_cfg=cfg) is None


def test_evaluate_emergency_higher_severity_wins():
    cfg = _rules([
        {"id": "low", "severity": 2, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
        {"id": "high", "severity": 4, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
    ])
    m = evaluate_emergency(user_text="x", canonicals_tr=[], rules_cfg=cfg)
    assert m is not None and m.rule_id == "high" and m.severity == 4


def test_evaluate_emergency_tiebreak_by_rule_id():
    # Equal severity → deterministic: smaller rule_id wins
    cfg = _rules([
        {"id": "b_tie", "severity": 3, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
        {"id": "a_tie", "severity": 3, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
    ])
    m = evaluate_emergency(user_text="x", canonicals_tr=[], rules_cfg=cfg)
    assert m is not None and m.rule_id == "a_tie"


def test_evaluate_emergency_later_rule_skipped_when_not_better():
    # Covers the "condition False → continue without updating best" path.
    # `a_first` wins on entry; `b_second` hits but is neither higher severity
    # nor a smaller rule_id — tie-break leaves best unchanged.
    cfg = _rules([
        {"id": "a_first", "severity": 3, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
        {"id": "b_second", "severity": 3, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
        {"id": "c_lower_sev", "severity": 2, "keyword_any": ["x"], "title_tr": "t", "message_tr": "m"},
    ])
    m = evaluate_emergency(user_text="x", canonicals_tr=[], rules_cfg=cfg)
    assert m is not None and m.rule_id == "a_first"


def test_evaluate_emergency_empty_rules_list_returns_none():
    assert evaluate_emergency(user_text="anything", canonicals_tr=[], rules_cfg=_rules([])) is None


def test_evaluate_emergency_default_title_when_rule_missing_fields():
    cfg = _rules([{"id": "rmin", "severity": 3, "keyword_any": ["x"]}])
    m = evaluate_emergency(user_text="x", canonicals_tr=[], rules_cfg=cfg)
    assert m is not None
    assert m.title_tr == "Acil durum şüphesi"
    assert m.message_tr == ""
    assert m.recommendation_tr == "112 / Acil Servis"


# ─── Smoke integration: real config/emergency_rules.json ──────────────

def test_evaluate_emergency_with_production_rules_smoke():
    """
    Uses the real production rule set to guard against shape drift.
    No exception = contract intact. Skipped if file missing.
    """
    # Rules live at repo root under config/. Tests normally run with
    # cwd=backend/, so probe both layouts.
    candidates = [Path("config/emergency_rules.json"), Path("../config/emergency_rules.json")]
    rules_path = next((p for p in candidates if p.exists()), None)
    if rules_path is None:
        pytest.skip("config/emergency_rules.json not present in this checkout")

    rules = load_emergency_rules(str(rules_path))
    # Benign input should not trigger any rule
    out = evaluate_emergency(
        user_text="hafif baş ağrım var",
        canonicals_tr=["başağrısı"],
        rules_cfg=rules,
    )
    assert out is None or isinstance(out, EmergencyMatch)
