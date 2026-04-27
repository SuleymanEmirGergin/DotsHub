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


# ─── Pre-launch audit pass ────────────────────────────────────────────
#
# A second sweep over the remaining hard triggers found more natural
# Turkish phrasings that fell through. These tests cover:
#   - breathing_severe: nefesim yetmiyor / soluğum kesildi / çok zor nefes
#   - syncope: kendimden geçtim / bilincim gitti
#   - gi_bleeding: siyah dışkı / dışkımda kan / kanlı kustum
#   - anaphylaxis: dilim şişti / boğazım kapandı
#   - blood_in_sputum: öksürürken kan geldi / balgamımda kan
#   - worst_headache: en kötü baş ağrısı
#
# Each set includes the new natural form AND an existing form to make
# sure the regex broadening did not break the original match.

@pytest.mark.parametrize(
    "phrase",
    [
        "nefesim yetmiyor",            # most common Turkish dyspnea phrase — was missed
        "çok zor nefes alıyorum",
        "soluğum kesildi",
        "nefes alamıyorum",            # existing
        "morardım",                    # existing
    ],
)
def test_breathing_severe_audit_pass(rules_json, phrase):
    assert _fire(rules_json, phrase) == "breathing_severe"


@pytest.mark.parametrize(
    "phrase",
    [
        "kendimden geçtim",            # most common Turkish fainting idiom — was missed
        "bilincim gitti",
        "bayıldım",                    # existing
        "bilincim kapandı",            # existing
    ],
)
def test_syncope_audit_pass(rules_json, phrase):
    assert _fire(rules_json, phrase) == "syncope"


@pytest.mark.parametrize(
    "phrase",
    [
        "en kötü baş ağrısı",          # users say "kötü" as well as "şiddetli"
        "hayatımın en kötü baş ağrısı",
        "hayatımın en şiddetli baş ağrısı",   # existing
    ],
)
def test_worst_headache_audit_pass(rules_json, phrase):
    assert _fire(rules_json, phrase) == "worst_headache"


@pytest.mark.parametrize(
    "phrase",
    [
        "siyah dışkı",                 # bare melena phrase, no possessive
        "dışkımda kan var",            # 1st-poss locative for hematochezia
        "kanlı kustum",                # word-reorder of "kan kustum"
        "kan kustum",                  # existing
        "katran gibi dışkı",           # existing pattern fallback
    ],
)
def test_gi_bleeding_audit_pass(rules_json, phrase):
    assert _fire(rules_json, phrase) == "gi_bleeding"


@pytest.mark.parametrize(
    "phrase",
    [
        "dilim şişti",                 # tongue swelling — textbook anaphylaxis
        "boğazım kapandı",             # airway closure — primary anaphylaxis sign
        "boğazım daraldı",
        "dudaklarım şişti",            # existing
        "anafilaksi",                  # existing
    ],
)
def test_anaphylaxis_audit_pass(rules_json, phrase):
    assert _fire(rules_json, phrase) == "anaphylaxis"


@pytest.mark.parametrize(
    "phrase",
    [
        "öksürürken kan geldi",        # past-tense subordinate clause — keyword fallback
        "balgamımda kan var",          # 1st-poss locative — regex
        "kanlı balgam",                # existing
        "kan tükürüyorum",             # existing
    ],
)
def test_blood_in_sputum_audit_pass(rules_json, phrase):
    assert _fire(rules_json, phrase) == "blood_in_sputum"


def test_blood_in_sputum_does_not_overfire_pulmonology_hemoptysis_scenario(rules_json):
    """The golden flow `pulmonology_hemoptysis.json` uses the present-tense
    `Öksürürken kan geliyor` to test the soft pulmonology (TB-workup) pathway.
    Adding a regex for that phrasing would route it to ER and break the
    scenario. We deliberately did NOT add that regex; this test locks the
    decision so a future "complete the verb forms" PR doesn't silently
    regress the pulmonology coverage. If you want hemoptysis-as-ER for the
    `geliyor` form, update tests/golden_flows/pulmonology_hemoptysis.json
    AND docs/medical/coverage_audit.md in the same PR.
    """
    assert _fire(rules_json, "Öksürürken kan geliyor") is None


# ─── Audit-pass negatives ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "phrase",
    [
        "biraz nefes nefese kaldım merdivende",  # mild exertional dyspnea, not ER
        "dilim ısırdım",                          # bit my tongue, not swelling
        "baş ağrım var",                          # mild headache, not "the worst"
        "siyah önlük giydim",                     # color word with no GI context
        "balgam çıkardım",                        # cough w/ phlegm, no blood
    ],
)
def test_audit_pass_no_false_positives(rules_json, phrase):
    rid = _fire(rules_json, phrase)
    assert rid is None, (
        f"unexpected emergency rule {rid!r} fired on benign phrase {phrase!r}"
    )


# ─── Documented accepted false-positive ──────────────────────────────
#
# `kendimden geçtim` is also an idiom for emotional/musical ecstasy
# ("I was lost in music"). In a medical-triage app this metaphorical
# use is essentially absent — patients open the app to report symptoms,
# not to comment on music. ER over-recommendation is the safer-side
# failure mode for safety_guard. We assert the over-trigger here so
# any future regex tightening that drops it shows up in CI as a
# behavior change rather than a silent regression.

def test_kendimden_gectim_idiom_overtriggers_safely(rules_json):
    """Documented over-trigger. If you broaden context to suppress
    this, please update this test rather than deleting it — we want
    the change to surface in code review.
    """
    rid = _fire(rules_json, "müzikte kendimden geçtim")
    assert rid == "syncope", (
        "kendimden geçtim idiom now suppressed — verify this is intentional"
    )
