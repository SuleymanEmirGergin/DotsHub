"""Adaptive negation-window regression for ``is_negated``.

Pins the bidirectional clause-bounded scan added to
``app.canonical_extract.is_negated``:

  - LEFT and RIGHT of the match are both inspected when ``end_idx`` is
    supplied (production path always supplies it via ``m.end()``).
  - Each side is truncated at the nearest adversative conjunction
    (``ama``/``fakat``/``ancak``) so postfix negation in the next
    clause doesn't bleed into the current one.
  - When ``end_idx`` is omitted the historical left-only contract
    holds — preserving callers that don't have a match end on hand.

Right-side scan exists because Turkish is predicate-final: "ateş yok"
is the natural negation form, not "yok ateş". Before this fix the
extractor silently treated "ateş yok" as a positive symptom.
"""
from __future__ import annotations

from app.canonical_extract import (
    DEFAULT_NEGATIONS,
    extract_canonicals_tr,
    is_negated,
    normalize_text_tr,
)


SYN = {"synonyms": [{"canonical": "ateş", "variants_tr": []}]}


# ─── postfix negation (Turkish-natural form) ───────────────────────

def test_postfix_yok_is_detected():
    assert "ateş" not in extract_canonicals_tr("ateş yok", {}, SYN)


def test_postfix_değil_is_detected():
    assert "ateş" not in extract_canonicals_tr("ateş değil", {}, SYN)


def test_postfix_negation_with_trailing_clause():
    # "ateş yok ama başım ağrıyor" — "yok" still applies to ateş;
    # "ama" only stops further-right scanning, not the immediate one.
    assert "ateş" not in extract_canonicals_tr(
        "ateş yok ama başım ağrıyor", {}, SYN
    )


def test_postfix_negation_separated_by_conjunction_does_not_apply():
    # "ateş var ama soğuk algınlığı yok" — "yok" is for the next
    # clause, "ateş" stays positive.
    assert "ateş" in extract_canonicals_tr(
        "ateş var ama soğuk algınlığı yok", {}, SYN
    )


def test_prefix_negation_still_works():
    # Pre-existing left-side behavior: "yok ateş" still negates.
    assert "ateş" not in extract_canonicals_tr("yok ateş", {}, SYN)


def test_double_negation_left_and_right():
    # Both sides flag negation — once is enough.
    assert "ateş" not in extract_canonicals_tr("hayır ateş yok", {}, SYN)


def test_negation_in_previous_clause_doesnt_bleed():
    # "üşüme yok ama ateş var" — "yok" lives in the previous clause,
    # bounded by "ama". Ateş stays positive.
    assert "ateş" in extract_canonicals_tr(
        "üşüme yok ama ateş var", {}, SYN
    )


# ─── unit-level is_negated calls (with end_idx) ────────────────────

def test_is_negated_detects_postfix_yok_with_end_idx():
    text = normalize_text_tr("ateş yok şu an")
    start = text.find("ateş")
    end = start + len("ateş")
    assert is_negated(text, start, DEFAULT_NEGATIONS, end_idx=end)


def test_is_negated_truncates_right_at_adversative():
    # Right-side window contains "ama yok"; "ama" terminates the
    # window before "yok" is reached.
    text = normalize_text_tr("ateş ama yok")
    start = text.find("ateş")
    end = start + len("ateş")
    assert not is_negated(text, start, DEFAULT_NEGATIONS, end_idx=end)


def test_is_negated_truncates_left_at_adversative():
    # Left-side window contains "yok ama X"; "ama" terminates the
    # window so "yok" doesn't apply to the post-ama match.
    text = normalize_text_tr("yok ama ateş")
    start = text.find("ateş")
    end = start + len("ateş")
    assert not is_negated(text, start, DEFAULT_NEGATIONS, end_idx=end)


def test_is_negated_left_only_when_end_idx_omitted():
    # Backward compat: callers that don't supply end_idx keep the
    # historical left-only behavior. "ateş yok" with start=0 has no
    # left content, so without end_idx → not negated.
    text = normalize_text_tr("ateş yok şu an")
    start = text.find("ateş")
    assert not is_negated(text, start, DEFAULT_NEGATIONS)


# ─── window cap still respected ────────────────────────────────────

def test_is_negated_right_window_cap_respected():
    # "yok" lives ~22 chars after the match; default window=18 keeps
    # it out of reach without an adversative bridge.
    text = "ateş şu an çok yüksek seviyede yok ben hissetmiyorum"
    start = text.find("ateş")
    end = start + len("ateş")
    assert not is_negated(text, start, DEFAULT_NEGATIONS, end_idx=end)


def test_is_negated_right_window_within_cap():
    # "yok" within 5 chars of match end — well inside default window.
    text = "ateş yok"
    start = text.find("ateş")
    end = start + len("ateş")
    assert is_negated(text, start, DEFAULT_NEGATIONS, end_idx=end)
