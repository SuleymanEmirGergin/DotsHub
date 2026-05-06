"""Turkish suffix-aware extraction regression.

Pins the morphology fix in ``app.canonical_extract``: the regex builder
appends a Turkish noun-suffix tail before the trailing ``\\b`` so a
variant stem like ``karnım`` matches the inflected ``karnımda``. Before
the fix, the substring fallback in ``scoring_v2`` masked the broken
extraction; this suite locks the extraction layer so future regressions
surface here instead of leaking into specialty scoring.

The 5 input strings come from the chip-2 bug brief — every one returned
``[]`` from ``extract_canonicals_tr`` against a stem-shaped synonym
dictionary. The dictionary used here is synthetic so the assertions
stay deterministic across synonym data tweaks. Real-corpus coverage is
guarded separately (``test_real_corpus``, ``test_golden_flows``).

Edge-case suite covers:
  - short stems (``kol``, ``el``, ``göz``) — must NOT over-match
    lookalikes like ``kolay``, ``elma``, ``gözle``, but MUST match
    legitimate inflections (``kolda``, ``elim``, ``gözüm``).
  - vowel-ending variants (``mide`` family).
  - plural suffixes (``-lar``/``-ler``).
"""
from __future__ import annotations

from app.canonical_extract import build_synonym_patterns, extract_canonicals_tr


# ─── confirmed failing cases from the chip-2 bug brief ─────────────

BUG_BRIEF_SYN = {
    "synonyms": [
        {"canonical": "karın ağrısı", "variants_tr": ["karnım", "karnım ağrıyor"]},
        {"canonical": "kulak ağrısı", "variants_tr": ["kulağım", "kulak"]},
        {"canonical": "boğaz ağrısı", "variants_tr": ["boğazım", "boğazım yanıyor"]},
        {"canonical": "sırt ağrısı", "variants_tr": ["sırtım", "sırt"]},
        {"canonical": "mide rahatsızlığı", "variants_tr": ["midem", "midede rahatsızlık"]},
    ]
}


def test_karnimda_matches_karin_agrisi():
    out = extract_canonicals_tr("karnımda ağrı var", {}, BUG_BRIEF_SYN)
    assert "karın ağrısı" in out


def test_kulagim_matches_kulak_agrisi():
    out = extract_canonicals_tr("kulağım ağrıyor", {}, BUG_BRIEF_SYN)
    assert "kulak ağrısı" in out


def test_bogazim_yaniyor_matches_bogaz_agrisi():
    out = extract_canonicals_tr("boğazım yanıyor", {}, BUG_BRIEF_SYN)
    assert "boğaz ağrısı" in out


def test_sirtimda_matches_sirt_agrisi():
    out = extract_canonicals_tr("sırtımda ağrı", {}, BUG_BRIEF_SYN)
    assert "sırt ağrısı" in out


def test_midemde_matches_mide_rahatsizligi():
    out = extract_canonicals_tr("midemde rahatsızlık", {}, BUG_BRIEF_SYN)
    assert "mide rahatsızlığı" in out


# ─── short-stem over-match guards ──────────────────────────────────
#
# The brief explicitly forbids `\w*` because short stems would soak up
# unrelated words. Pin the negative cases so future suffix list growth
# doesn't silently regress this property.

SHORT_STEM_SYN = {
    "synonyms": [
        {"canonical": "kol kırığı", "variants_tr": ["kol"]},
        {"canonical": "göz hastalığı", "variants_tr": ["göz"]},
        {"canonical": "el yarası", "variants_tr": ["el"]},
    ]
}


def test_short_stem_kol_does_not_match_kolay():
    out = extract_canonicals_tr("kolay yöntem ile çözüldü", {}, SHORT_STEM_SYN)
    assert out == []


def test_short_stem_goz_does_not_match_gozle():
    out = extract_canonicals_tr("gözle görmek mümkün değil", {}, SHORT_STEM_SYN)
    assert out == []


def test_short_stem_el_does_not_match_elma():
    out = extract_canonicals_tr("elma yedim bugün", {}, SHORT_STEM_SYN)
    assert out == []


def test_short_stem_kol_matches_locative_kolda():
    out = extract_canonicals_tr("kolda şiddetli ağrı", {}, SHORT_STEM_SYN)
    assert "kol kırığı" in out


def test_short_stem_el_matches_possessive_elim():
    out = extract_canonicals_tr("elim çok ağrıyor", {}, SHORT_STEM_SYN)
    assert "el yarası" in out


def test_short_stem_goz_matches_possessive_gozum():
    out = extract_canonicals_tr("gözüm kızardı", {}, SHORT_STEM_SYN)
    assert "göz hastalığı" in out


# ─── vowel-ending variants ─────────────────────────────────────────

VOWEL_END_SYN = {
    "synonyms": [
        {"canonical": "mide şikayeti", "variants_tr": ["mide", "midem"]},
        {"canonical": "burun akıntısı", "variants_tr": ["burnu", "burnum"]},
    ]
}


def test_vowel_ending_mide_matches_locative():
    out = extract_canonicals_tr("midede yanma var", {}, VOWEL_END_SYN)
    assert "mide şikayeti" in out


def test_vowel_ending_midem_matches_locative_midemde():
    out = extract_canonicals_tr("midemde rahatsızlık", {}, VOWEL_END_SYN)
    assert "mide şikayeti" in out


# ─── plural suffix matching ────────────────────────────────────────

PLURAL_SYN = {
    "synonyms": [
        {"canonical": "ateş", "variants_tr": []},
        {"canonical": "ağrı", "variants_tr": []},
    ]
}


def test_plural_ler_matches_stem():
    out = extract_canonicals_tr("ateşler arttı geceleri", {}, PLURAL_SYN)
    assert "ateş" in out


def test_plural_lar_matches_stem():
    out = extract_canonicals_tr("ağrılar başladı sabah", {}, PLURAL_SYN)
    assert "ağrı" in out


# ─── word-boundary preserved ───────────────────────────────────────
#
# This is the contract the original `\b...\b` was protecting. The fix
# adds an OPTIONAL suffix tail before the trailing `\b`, so unrelated
# stems-as-prefixes must still NOT match. Specifically: `ateşle` (with
# the case suffix `-le`, not in our cap list) must not match `ateş`.

def test_word_boundary_still_rejects_unsupported_suffix():
    syn = {"synonyms": [{"canonical": "ateş", "variants_tr": []}]}
    pat = build_synonym_patterns(syn)[0][1]
    assert pat.search("ateşle gel") is None
    # Sanity — supported inflections still match.
    assert pat.search("yüksek ateş var") is not None
    assert pat.search("ateşim var") is not None
    assert pat.search("ateşler arttı") is not None
