"""Turkish-morphology regression tests for emergency hard triggers.

Background — these patterns previously missed natural Turkish forms:

  1) Vowel elision: `göğüs` (chest) drops the second `ü` when a possessive
     suffix is added → `göğsüm`, `göğsümde`. The original regex
     `göğüs(üm|ümde)?` only matched the non-elided spelling, which Turkish
     speakers do NOT use in real text.

  2) 1st-person possessive on body parts paired with action verbs:
     `sol kola vuruyor` (radiates to the arm) is what the rule was written
     for, but actual users describing themselves type
     `sol koluma vuruyor` (radiates to MY arm). Same root, different case.

  3) Stroke arm-weakness paired with 1st-person verb suffix:
     `kolu(nu) kaldıramıyor` only catches 3rd-person reports
     ("they can't lift their arm"). A self-describing user says
     `kolumu kaldıramıyorum` — accusative-possessive + 1st-person verb.

A demo-script chest-pain emergency phrase exercised all three gaps at once
and fell through to non-emergency routing. These tests lock in the fix.

The rule patterns live in backend/app/data/rules.json. Both the demo phrase
file (demo_chest_emergency.json) and DEMO_SCRIPT.md are downstream artefacts
— do not modify them to "fix" this; the bug is in the patterns.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.safety_guard import safety_guard_check


@pytest.fixture(scope="module")
def rules_json():
    path = Path(__file__).resolve().parent.parent / "app" / "data" / "rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _fire(rules_json, text: str):
    """Run the safety guard on free text; return rule_id or None."""
    out = safety_guard_check(text, {}, rules_json)
    return out["rule_id"] if out else None


# ─── Demo phrase from DEMO_SCRIPT — must fire ─────────────────────────

def test_demo_chest_emergency_phrase_fires(rules_json):
    """The exact natural Turkish phrase from the demo MUST trigger ER_NOW.

    Combines two morphology issues at once: vowel-elided `göğsümde` and
    1st-person possessive `koluma`. Either one fixed alone is enough to
    fire (arm-radiation path catches it), but both should be matched.
    """
    rid = _fire(
        rules_json,
        "göğsümde şiddetli bir sıkışma var, sol koluma vuruyor",
    )
    assert rid == "chest_pressure_sweating"


# ─── 1) Vowel elision: göğüs → göğs ───────────────────────────────────

@pytest.mark.parametrize(
    "phrase",
    [
        "göğsümde baskı var",
        "göğsüm ağrıyor",
        "göğsümde ağrı",
        # non-elided still works
        "göğüs ağrım var",
        "göğüs ağrısı çok şiddetli",
    ],
)
def test_chest_pressure_sweating_vowel_elision(rules_json, phrase):
    assert _fire(rules_json, phrase) == "chest_pressure_sweating"


# ─── 2) Possessive arm-radiation: kola → koluma ───────────────────────

@pytest.mark.parametrize(
    "phrase",
    [
        "sol kola vuruyor",            # bare dative, was already covered
        "sol koluma vuruyor",          # 1st-person possessive dative
        "sol kola vurdu",              # past tense
        "sol koluma vurdu",            # past tense, 1st-pers poss
        "ağrı sol koluma vuruyor",     # full natural sentence
    ],
)
def test_chest_pressure_sweating_arm_possessive(rules_json, phrase):
    assert _fire(rules_json, phrase) == "chest_pressure_sweating"


# ─── 3) Possessive jaw-radiation: çene(me|ye) ─────────────────────────

@pytest.mark.parametrize(
    "phrase",
    [
        "çeneme vuruyor",              # was already covered
        "çeneye vuruyor",              # bare dative — newly covered
        "çeneme vurdu",
        "çeneye vurdu",
    ],
)
def test_chest_pressure_sweating_jaw_dative(rules_json, phrase):
    assert _fire(rules_json, phrase) == "chest_pressure_sweating"


# ─── 4) chest_pain_plus_breathlessness: same elision fix ──────────────

@pytest.mark.parametrize(
    "phrase",
    [
        "göğsümde baskı ve şiddetli nefes darlığı",
        "göğsüm ağrıyor, nefesim yetmiyor",
        # non-elided still works
        "göğüs ağrı ile birlikte nefes darlığı",
    ],
)
def test_chest_pain_plus_breathlessness_elision(rules_json, phrase):
    """All of these are ER_NOW. Either chest_pain_plus_breathlessness or
    chest_pressure_sweating may fire first — both are valid; what matters
    is that *some* hard trigger fires. Iteration order in safety_guard.py
    picks the first match, so we just assert one of the chest-pain rules.
    """
    rid = _fire(rules_json, phrase)
    assert rid in {"chest_pain_plus_breathlessness", "chest_pressure_sweating", "breathing_severe"}, (
        f"expected a chest/breathing emergency rule for {phrase!r}, got {rid!r}"
    )


# ─── 5) stroke_signs: 1st-person possessive arm + 1st-person verb ─────

@pytest.mark.parametrize(
    "phrase",
    [
        "kolumu kaldıramıyorum",       # 1st-poss-acc + 1st-pers verb
        "kolunu kaldıramıyor",         # 3rd-poss-acc + 3rd-pers verb (existing)
        "kolu güçsüzleşti",            # existing
        "kolum güçsüzleşti",           # 1st-poss-nom — newly covered
        "kolum güçsüzleştim",          # over-permissive but harmless
    ],
)
def test_stroke_signs_arm_possessive(rules_json, phrase):
    assert _fire(rules_json, phrase) == "stroke_signs"


# ─── 6) Negatives: must NOT trigger ───────────────────────────────────

@pytest.mark.parametrize(
    "phrase",
    [
        # near-but-benign — body part without ER context
        "göğsüm sıcak",                # warm chest, not pain
        "göğsüm güzel görünüyor",      # cosmetic comment
        "göğüs kafesi anatomisi",      # anatomy reading
        # arm without radiation/weakness verb
        "kolumu yıkadım",              # I washed my arm
        "kolum üşüdü",                 # my arm got cold
        "sol koluma dövme yaptırdım",  # I got a tattoo on my left arm
        # jaw without radiation
        "çenem küçük",                 # my jaw is small
        # routine complaints
        "hafif baş ağrım var",
        "burnum akıyor",
        "midem bulanıyor biraz",
    ],
)
def test_no_false_positive_on_benign_phrases(rules_json, phrase):
    rid = _fire(rules_json, phrase)
    assert rid is None, f"unexpected emergency rule {rid!r} fired on benign phrase {phrase!r}"


# ─── 7) Demo answers-aggregation path also benefits ───────────────────

def test_demo_phrase_via_answers_aggregation(rules_json):
    """safety_guard concatenates answer values into the search text.
    A user who describes the emergency in an answer field should also
    trigger after the morphology fix.
    """
    out = safety_guard_check(
        "merhaba",
        {"chief_complaint": "göğsümde sıkışma, sol koluma vuruyor"},
        rules_json,
    )
    assert out is not None
    assert out["rule_id"] == "chest_pressure_sweating"
