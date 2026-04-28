"""Branch coverage for app.canonical_extract.

Every branch of the Turkish NLU extractor:
  - tr_lower: Turkish-aware "I"/"İ" mapping.
  - normalize_text_tr: lowercase, punctuation stripping, whitespace
    collapse.
  - build_synonym_patterns: entries without canonical skipped, blank
    variants skipped, canonical-itself self-match, length-desc
    ordering, dedup across duplicate (canonical, phrase) pairs.
  - is_negated: any negation token in the window; nothing in the
    window; empty/blank negation string skipped.
  - extract_canonicals_tr: free-text hits added, negated hits
    skipped, answer keys injected, answers=None tolerated, blank
    answer keys skipped, stable sorted output.

Keeps the module pinned against the golden-flow fixtures — if the
regex word-boundary or the Turkish lowercase table ever regresses,
this suite fails before the slow-running synonym-audit scenarios do.
"""
from __future__ import annotations

import re

from app.canonical_extract import (
    DEFAULT_NEGATIONS,
    build_synonym_patterns,
    extract_canonicals_tr,
    is_negated,
    normalize_text_tr,
    tr_lower,
)


# ─── tr_lower ────────────────────────────────────────────────────────

def test_tr_lower_handles_turkish_i_variants():
    # Plain str.lower() turns "I" into "i" and "İ" into "İ"; the
    # Turkish-aware map correctly yields "ı" and "i" respectively.
    assert tr_lower("ISLAK") == "ıslak"
    assert tr_lower("İSTANBUL") == "istanbul"


def test_tr_lower_keeps_lowercase_unchanged():
    assert tr_lower("baş ağrısı") == "baş ağrısı"


# ─── normalize_text_tr ──────────────────────────────────────────────

def test_normalize_strips_punctuation_and_collapses_whitespace():
    assert normalize_text_tr("Başım,   çok  ağrıyor!") == "başım çok ağrıyor"


def test_normalize_preserves_turkish_letters():
    assert normalize_text_tr("Göğüs ağrısı") == "göğüs ağrısı"


def test_normalize_empty_input_returns_empty():
    assert normalize_text_tr("") == ""
    assert normalize_text_tr("   ") == ""


# ─── build_synonym_patterns ─────────────────────────────────────────

def test_build_patterns_skips_entries_without_canonical():
    syn = {"synonyms": [{"canonical": "", "variants_tr": ["foo"]}]}
    assert build_synonym_patterns(syn) == []


def test_build_patterns_skips_blank_variants():
    syn = {
        "synonyms": [
            {"canonical": "ateş", "variants_tr": ["", "   ", "yüksek ateş"]}
        ]
    }
    out = build_synonym_patterns(syn)
    # Expect: canonical self-match + one real variant = 2 patterns.
    assert len(out) == 2
    canonicals = [c for (c, _) in out]
    assert all(c == "ateş" for c in canonicals)


def test_build_patterns_orders_longer_phrases_first():
    syn = {
        "synonyms": [
            {
                "canonical": "baş ağrısı",
                "variants_tr": ["başım ağrıyor çok şiddetli", "baş ağrısı"],
            }
        ]
    }
    out = build_synonym_patterns(syn)
    phrase_lengths = [len(pat.pattern) for _, pat in out]
    assert phrase_lengths == sorted(phrase_lengths, reverse=True)


def test_build_patterns_dedupes_duplicate_canonical_phrase_pairs():
    syn = {
        "synonyms": [
            {"canonical": "ateş", "variants_tr": ["yüksek ateş"]},
            {"canonical": "ateş", "variants_tr": ["yüksek ateş"]},
        ]
    }
    out = build_synonym_patterns(syn)
    # 1 unique variant + 1 canonical self-match, both deduped.
    assert len(out) == 2


def test_build_patterns_compiles_word_boundary_regex():
    syn = {"synonyms": [{"canonical": "ateş", "variants_tr": []}]}
    out = build_synonym_patterns(syn)
    _, pat = out[0]
    assert isinstance(pat, re.Pattern)
    # START boundary still strict — "kateş" must NOT match (no in-word
    # match). Turkish has no prefixes, so leading `\b` stays as-is.
    assert pat.search("kateşim gel") is None
    # END boundary now tolerates Turkish trailing suffixes (loc, abl,
    # poss, etc.) per the morphology fix in canonical_extract.py.
    # "ateşle" (with fever, instrumental -le) and "ateşim" (1sg poss)
    # both correctly resolve to canonical "ateş".
    assert pat.search("ateşle birlikte gel") is not None
    assert pat.search("ateşim var") is not None
    assert pat.search("yüksek ateş var") is not None


# ─── is_negated ─────────────────────────────────────────────────────

def test_is_negated_detects_left_window_negation():
    text = normalize_text_tr("hayır ateş yok")
    idx = text.find("ateş")
    # "hayır" sits 6 chars before "ateş" — inside the 18-char window.
    assert is_negated(text, idx, DEFAULT_NEGATIONS)


def test_is_negated_ignores_right_side_negation():
    text = normalize_text_tr("ateş yok şu an")
    idx = text.find("ateş")
    # "yok" lives AFTER ateş here; the window only looks LEFT.
    assert not is_negated(text, idx, DEFAULT_NEGATIONS)


def test_is_negated_ignores_far_window():
    # is_negated peeks back only `window` chars (default 18). We pass
    # an already-normalized string with real content between the
    # negation and the match, so the default window excludes "değil".
    text = "değil kalp çarpıntısı başım dönüyor ateş yok"
    idx = text.find("ateş")
    # Window = text[idx-18 : idx] ≈ "pıntısı başım dönü"  — no negation.
    assert not is_negated(text, idx, DEFAULT_NEGATIONS)


def test_is_negated_tolerates_blank_negation_token():
    text = "ateş var"
    assert not is_negated(text, 0, ["", "   "])


# ─── extract_canonicals_tr ──────────────────────────────────────────

SIMPLE_SYN = {
    "synonyms": [
        {
            "canonical": "ateş",
            "variants_tr": ["yüksek ateş", "vücut sıcaklığı yüksek"],
        },
        {
            "canonical": "baş ağrısı",
            "variants_tr": ["başım ağrıyor"],
        },
    ]
}


def test_extract_finds_free_text_canonicals():
    out = extract_canonicals_tr(
        "Dün akşamdan beri başım ağrıyor ve yüksek ateş var.",
        {},
        SIMPLE_SYN,
    )
    assert "ateş" in out
    assert "baş ağrısı" in out


def test_extract_respects_negation():
    out = extract_canonicals_tr("değil ateş", {}, SIMPLE_SYN)
    assert "ateş" not in out


def test_extract_includes_answer_keys_as_canonicals():
    out = extract_canonicals_tr("", {"nefes darlığı": "evet"}, SIMPLE_SYN)
    assert "nefes darlığı" in out


def test_extract_tolerates_none_answers():
    # Defensive: some code paths pass None rather than {}.
    out = extract_canonicals_tr("yüksek ateş", None, SIMPLE_SYN)  # type: ignore[arg-type]
    assert out == ["ateş"]


def test_extract_skips_blank_answer_keys():
    out = extract_canonicals_tr("", {"": "evet", "   ": "evet"}, SIMPLE_SYN)
    assert out == []


def test_extract_returns_sorted_stable_output():
    out = extract_canonicals_tr(
        "yüksek ateş başım ağrıyor",
        {"nefes darlığı": "evet"},
        SIMPLE_SYN,
    )
    assert out == sorted(out)
    assert set(out) == {"ateş", "baş ağrısı", "nefes darlığı"}


def test_extract_handles_empty_synonyms_json():
    out = extract_canonicals_tr("yüksek ateş", {}, {"synonyms": []})
    assert out == []
