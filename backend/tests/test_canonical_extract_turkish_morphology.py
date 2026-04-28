"""Turkish morphology coverage for canonical extraction.

Regression suite for the suffix-tolerance fix in canonical_extract.py.
Before the fix, the trailing `\b` boundary in `\b{phrase}\b` failed
whenever the user attached a Turkish noun/verb suffix to the phrase's
last token — natural input like "sağ alt karın bölgemde keskin ağrı"
extracted ZERO canonicals because `bölgem` (variant) is followed by
`d` (\\w), so `\b` did not fire.

The fix appends an optional Turkish-suffix alternation between the
phrase end and the boundary. This file pins:
  - **positive cases**: 3-4 inflected forms per high-traffic canonical
    (locative, ablative, possessive, possessive+case, relative -ki,
    common verbal tense markers).
  - **negative cases**: idioms and unrelated phrases that contain a
    bare token from the canonical but should NOT match because the
    full phrase is absent (e.g., "karın doyurmak" — "to fill one's
    belly", an idiom unrelated to abdominal pain).

Failing this suite means the suffix list shrank or expanded into
greedy-false-positive territory — both regressions of the contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.canonical_extract import extract_canonicals_tr


# ─── Real synonyms_tr.json (production data, not a stub) ────────────
# We deliberately load the real synonym set so the test reflects what
# the orchestrator actually scores against. Stubbing would let the
# suffix list drift away from the data shapes the orchestrator sees.

_DATA = json.loads(
    (Path(__file__).resolve().parents[1] / "app" / "data" / "synonyms_tr.json")
    .read_text(encoding="utf-8")
)


def _extract(text: str) -> list[str]:
    return extract_canonicals_tr(text, {}, _DATA)


# ─── Positive cases: suffix tolerance per common canonical ──────────


@pytest.mark.parametrize(
    "text,expected_canonical",
    [
        # Original demo bug — "sağ alt karın bölgem" variant + locative `-de`.
        # This is the exact regression reported in the demo-script
        # validation that motivated the fix.
        (
            "iki gündür sağ alt karın bölgemde keskin bir ağrı var",
            "sağ alt karın ağrısı",
        ),
        # Same variant, different case markers
        ("sağ alt karın bölgemden başlayan ağrı", "sağ alt karın ağrısı"),
        ("sağ alt karın bölgeme vuran ağrı", "sağ alt karın ağrısı"),
    ],
)
def test_sag_alt_karin_agrisi_suffix_forms(text, expected_canonical):
    assert expected_canonical in _extract(text)


@pytest.mark.parametrize(
    "text",
    [
        # Variant "boğazım ağrıyor" + verbal past `-du`
        "boğazım ağrıyordu",
        # Variant "boğazım ağrıyor" + reported past `-muş`
        "boğazım ağrıyormuş",
        # Variant "bademciklerim şişti" — exact, control, must keep working
        "bademciklerim şişti",
    ],
)
def test_bogaz_agrisi_suffix_forms(text):
    assert "boğaz ağrısı" in _extract(text)


@pytest.mark.parametrize(
    "text",
    [
        # Variant "belim ağrıyor" + verbal past
        "belim ağrıyordu",
        # Variant "belim ağrıyor" + reported past
        "belim ağrıyormuş",
        # Bare canonical "bel ağrım" + accusative `-ı`
        "bel ağrımı dindiremiyorum",
        # Variant "belimde ağrı" + locative still attaching cleanly
        "belimde ağrıdan rahatsızım",
    ],
)
def test_bel_agrisi_suffix_forms(text):
    assert "bel ağrısı" in _extract(text)


@pytest.mark.parametrize(
    "text",
    [
        # Variant "başım ağrıyor" + verbal past
        "başım ağrıyordu",
        # Variant "başım ağrıyor" + reported past
        "başım ağrıyormuş",
        # Bare canonical "baş ağrısı" + locative
        "baş ağrısında ne yapmalıyım",
        # Bare canonical "baş ağrısı" + ablative
        "baş ağrısından çok rahatsızım",
    ],
)
def test_bas_agrisi_suffix_forms(text):
    assert "baş ağrısı" in _extract(text)


@pytest.mark.parametrize(
    "text",
    [
        # Bare canonical "ateş" + 1sg poss
        "ateşim var",  # also exact variant — control
        # Bare canonical "ateş" + locative
        "ateşte titriyorum",
        # Bare canonical "ateş" + ablative
        "ateşten yanıyorum",
        # Bare canonical "ateş" + accusative + 1sg poss → -imi
        "ateşimi düşürdüm",
    ],
)
def test_ates_suffix_forms(text):
    assert "ateş" in _extract(text)


@pytest.mark.parametrize(
    "text",
    [
        # Variant "kalbim çarpıyor" + verbal past
        "kalbim çarpıyordu",
        # Variant "çarpıntı hissediyorum" + reported past
        "çarpıntı hissediyormuş gibi",
        # Bare canonical "çarpıntı" + locative
        "çarpıntıda ne yaptın",
        # Bare canonical "çarpıntı" + ablative
        "çarpıntıdan korkuyorum",
    ],
)
def test_carpinti_suffix_forms(text):
    assert "çarpıntı" in _extract(text)


# ─── Negative cases: idioms & lookalikes that must NOT match ────────


@pytest.mark.parametrize(
    "text",
    [
        # "karın doyurmak" — Turkish idiom for "to fill one's belly"
        # (i.e., to eat). Has the bare token "karın" but no canonical
        # phrase; our patterns include "karın ağrısı" + variants that
        # all carry "ağrı"/"sancı"/etc., so this MUST stay empty.
        "akşam karın doyurmak için lokantaya gittik",
        # Bare "karın" without any pain qualifier at all
        "karın bölgesi anatomisi nedir",
        # "ateş etmek" — to fire (a weapon). Idiomatic, non-medical.
        # However, "ateş etmek" → contains "ateş" + "etmek". Our
        # pattern allows "ateş" + suffix, but "etmek" isn't a suffix.
        # The standalone "ateş" canonical pattern WILL fire here
        # because there's no negation context. This is acceptable —
        # the orchestrator's downstream context (no other symptoms)
        # will route correctly. Documenting as expected behavior:
        # we do NOT make this case fail-extraction; we only assert
        # non-extraction for the abdominal/musculoskeletal lookalikes
        # below where the canonical phrase is genuinely absent.
        # "ateş etmek için izin lazım",  # intentionally not asserted
        # "boğaza takılmak" — to choke on (food, idiom). No "boğaz
        # ağrısı" phrase appears, so no match expected.
        "balık kılçığı boğaza takıldı",
    ],
)
def test_idioms_and_lookalikes_do_not_match_abdominal_or_throat(text):
    out = _extract(text)
    assert "karın ağrısı" not in out
    assert "sağ alt karın ağrısı" not in out
    assert "boğaz ağrısı" not in out


def test_negation_still_works_for_suffixed_form():
    """Suffix tolerance must not bypass the negation window check.

    The variant "ateşim var" carries the canonical "ateş". When
    preceded by a negation token within the look-back window,
    the match must still be dropped — otherwise the fix would
    silently regress the negation safety contract.
    """
    out = _extract("değil ateşim")
    assert "ateş" not in out


def test_start_boundary_is_still_strict():
    """Turkish has no prefixes — the leading `\\b` must stay strict.

    A made-up word that *contains* "ateş" mid-token (e.g., "kateş")
    must NOT match. This guards against accidental greediness if the
    suffix logic ever migrates from the trailing edge to both ends.
    """
    out = _extract("kateşim gel")
    assert "ateş" not in out


# ─── Sanity: the exact demo phrase from the bug report ──────────────


def test_demo_phrase_extracts_at_least_one_canonical():
    """The phrase that surfaced the bug during demo validation.

    Before the fix this returned []. After the fix it must return at
    least one abdominal-pain canonical (the orchestrator's
    explainability trace claims to surface canonicals — empty list
    breaks that contract).
    """
    text = "iki gündür sağ alt karın bölgemde keskin bir ağrı var, yürümek de zorlaştı"
    out = _extract(text)
    assert len(out) >= 1, f"expected at least one canonical, got {out!r}"
    # And specifically the right-lower-quadrant abdominal-pain canonical
    # (the most-specific match given the synonym set).
    assert "sağ alt karın ağrısı" in out
