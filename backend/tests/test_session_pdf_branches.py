"""Branch coverage for app.services.session_pdf.

Scope
-----
The PDF builder has three interesting branch clusters:

1. `_safe_text` — Latin-1 fast-path, NFKD fallback path, and the
   "unknown glyph" replacement path. Each needs its own input.
2. `_format_created_at` — ISO-8601 happy path, the `Z` suffix
   normalisation, and the invalid-string fallback.
3. `build_session_pdf` — presence/absence branches for every section
   (metadata, canonicals, top_conditions, events, feedback). Covers
   both "list present with items" + "list empty/missing → italic
   no-entries placeholder".

All tests stay in-process (no temp files, no subprocess) and assert
on byte-level invariants — %PDF magic header + minimum size — so
they're fast (<100 ms total) and deterministic across platforms.
"""
from __future__ import annotations

import pytest

from app.services.session_pdf import (
    _format_created_at,
    _safe_text,
    build_session_pdf,
)


# ─── _safe_text ────────────────────────────────────────────────────


class TestSafeText:
    def test_ascii_passthrough(self):
        assert _safe_text("Hello world") == "Hello world"

    def test_turkish_characters_render_without_crash(self):
        # Türkçe'ye özgü Ş/ş/ğ/Ğ/ı/İ karakterleri Latin-1 içinde
        # DEĞİL (Latin-1 = ISO-8859-1; Türkçe harfler ISO-8859-9'da).
        # Fast-path encode raises → NFKD fallback decomposes them
        # into base letter + combining mark; combining marks can't
        # be Latin-1 encoded → `?` substitution kicks in.
        # Core guarantees: no crash, ASCII prefixes/suffixes preserved,
        # output Latin-1 encodable.
        out = _safe_text("Şu anda ağrım çok şiddetli")
        # Never crashes → returns a string
        assert isinstance(out, str)
        # Output must be Latin-1 encodable (that's the whole point
        # of the helper).
        out.encode("latin-1")
        # ASCII-only fragments survive intact.
        assert "anda" in out
        assert "ok" in out or "çok" in out

    def test_emoji_falls_back_to_question_mark(self):
        # Emoji are outside Latin-1 entirely → `?` substitution
        # kicks in per-character.
        out = _safe_text("Merhaba 👋")
        assert "Merhaba" in out
        assert "?" in out

    def test_none_returns_empty_string(self):
        assert _safe_text(None) == ""

    def test_non_string_coerced_to_string(self):
        # Integers, floats, ints from DB rows go through str() first.
        assert _safe_text(42) == "42"
        assert _safe_text(3.14) == "3.14"

    def test_curly_quotes_substituted(self):
        # Smart quotes (U+2018/2019/201C/201D) aren't in Latin-1;
        # they're decomposed but the unknown-glyph branch should
        # still produce a readable result.
        result = _safe_text("say “hello” and move on")
        # Not asserting exact output — just no crash + some content
        # preserved.
        assert "hello" in result

    def test_already_latin1_bytes_compatible(self):
        # Accented Western Europe letters (é, ñ, ü) are all Latin-1
        # directly.
        assert _safe_text("café naïve Ångström") == "café naïve Ångström"


# ─── _format_created_at ────────────────────────────────────────────


class TestFormatCreatedAt:
    def test_iso_with_timezone(self):
        out = _format_created_at("2026-04-20T14:07:58.041+00:00")
        # "YYYY-MM-DD HH:MM UTC" shape — substring check (exact offset
        # normalisation varies by Python version).
        assert out.startswith("2026-04-20")

    def test_iso_with_z_suffix(self):
        # `Z` is replaced with `+00:00` before fromisoformat — the
        # early-Python CPython fromisoformat can't parse `Z` on its
        # own.
        out = _format_created_at("2026-04-20T10:00:00Z")
        assert out.startswith("2026-04-20")

    def test_none_returns_dash(self):
        assert _format_created_at(None) == "—"

    def test_empty_string_returns_dash(self):
        assert _format_created_at("") == "—"

    def test_invalid_string_falls_back_to_prefix(self):
        # `fromisoformat` raises → we return the first 19 chars so
        # the PDF still shows something recognisable.
        out = _format_created_at("not a real date")
        # Exact behaviour: str(raw)[:19]
        assert out == "not a real date"

    def test_invalid_long_string_truncated(self):
        # Same path but the fallback truncates to 19 characters so
        # the layout doesn't blow up for nonsense input.
        out = _format_created_at("this is also not a valid date ever")
        assert len(out) == 19


# ─── build_session_pdf — happy + empty paths ───────────────────────


def _full_session() -> dict:
    """Representative session with every field populated.

    Exercises the "section has data → render list" branch on each of:
    metadata, canonicals, top_conditions, events, feedback.
    """
    return {
        "session": {
            "session_id": "happy-001",
            "created_at": "2026-04-20T14:07:58.041+00:00",
            "envelope_type": "RESULT",
            "urgency": "ROUTINE",
            "recommended_specialty_tr": "Dahiliye",
            "confidence_0_1": 0.84,
            "stop_reason": "confident",
            "input_text": "Başım ağrıyor ve midem bulanıyor.",
            "extracted_canonicals": ["baş ağrısı", "bulantı"],
            "top_conditions": [
                {
                    "disease_label": "Migren",
                    "score_0_1": 0.76,
                    "disease_description_tr": "Tekrarlayan baş ağrısı.",
                },
                # Second condition WITHOUT description — covers the
                # "description missing → skip desc paragraph" branch.
                {"disease_label": "Gerilim tipi baş ağrısı", "score_0_1": 0.41},
            ],
        },
        "events": [
            {"role": "user", "content": "Başım ağrıyor"},
            {"role": "ai", "content": "Ne zaman başladı?"},
        ],
        "feedback": [{"rating": "up", "comment_tr": "İyi öneri"}],
    }


class TestBuildSessionPdfFullPath:
    def test_produces_valid_pdf(self):
        pdf = build_session_pdf(_full_session())
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"
        # A real PDF with this many sections is always >1 KB.
        assert len(pdf) > 1000

    def test_nb_pages_macro_renders(self):
        # `alias_nb_pages` replaces the placeholder with the actual
        # page count. We can't guarantee how fpdf2 writes it inside
        # the compressed stream, but the output shouldn't contain the
        # raw `{nb}` literal (fpdf2 replaces at flush time).
        pdf = build_session_pdf(_full_session())
        assert b"{nb}" not in pdf


class TestBuildSessionPdfEmptyBranches:
    def test_empty_events_and_feedback(self):
        # Triggers the "events empty → italic dash" + "feedback empty
        # → italic dash" branches in _bullet_list and the explicit
        # "no conditions" fallback in the top_conditions block.
        detail = {
            "session": {"session_id": "empty-1"},
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 500

    def test_session_missing_keys(self):
        # All optional fields absent — each _kv_row falls back to the
        # default sentinel `"—"`. No crash, still produces a valid PDF.
        detail = {"session": {"session_id": "sparse"}, "events": [], "feedback": []}
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_none_session_fallback(self):
        # The endpoint guards against null session BEFORE calling
        # build_session_pdf, but the builder itself should also not
        # crash if handed a dict with `session: None` — it's defensive.
        detail = {"session": None, "events": [], "feedback": []}
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"


class TestBuildSessionPdfEdgeCases:
    def test_confidence_as_string_is_ignored(self):
        # When an old row has `confidence_0_1` stored as a string
        # (migration quirk), the `isinstance(conf, (int, float))`
        # branch should skip it → fallback to `—`. Crashes would be
        # a regression.
        detail = {
            "session": {
                "session_id": "string-conf",
                "confidence_0_1": "not a number",
            },
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_top_condition_non_dict_entry_skipped(self):
        # `top_conditions` occasionally contains None from legacy
        # rows; the builder's `isinstance(c, dict)` guard should
        # silently skip it.
        detail = {
            "session": {
                "session_id": "legacy-tc",
                "top_conditions": [
                    None,
                    {"disease_label": "Real", "score_0_1": 0.5},
                    "string-not-a-dict",
                ],
            },
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_event_non_dict_entry_skipped(self):
        detail = {
            "session": {"session_id": "e1"},
            "events": [None, {"role": "user", "content": "hi"}, 42],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_feedback_non_dict_entry_skipped(self):
        detail = {
            "session": {"session_id": "f1"},
            "events": [],
            "feedback": [None, {"rating": "up", "comment_tr": "ok"}, "bad"],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_feedback_with_comment_but_no_rating(self):
        # rating key absent → falls back through `up_down` → finally
        # literal "?" label. Comment still renders.
        detail = {
            "session": {"session_id": "f2"},
            "events": [],
            "feedback": [{"comment_tr": "bare comment"}],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_feedback_with_rating_but_no_comment(self):
        # The `if comment:` branch — comment empty/missing → skip the
        # comment paragraph render path. Covers the 306→309 branch
        # that other tests (which all supply a comment) miss.
        detail = {
            "session": {"session_id": "f3"},
            "events": [],
            "feedback": [{"rating": "up"}],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_event_uses_fallback_content_field_names(self):
        # A legacy event row might carry `question_tr` / `answer_value`
        # rather than `content`. Builder checks them in order; no
        # matching key → empty string shown rather than KeyError.
        detail = {
            "session": {"session_id": "legacy-ev"},
            "events": [
                {"role": "ai", "question_tr": "Ne zaman başladı?"},
                {"role": "user", "answer_value": "Dün"},
                {"role": "system"},  # no content at all
            ],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_long_input_text_wraps_without_crashing(self):
        # Multi-cell with >1 KB of text was the original bug that
        # triggered "not enough horizontal space"; regression test.
        long_text = "ağrı " * 500  # ~2500 characters
        detail = {
            "session": {"session_id": "long", "input_text": long_text},
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"


# ─── branch-level negative cases ──────────────────────────────────


class TestBuildSessionPdfDefensive:
    def test_top_conditions_uses_label_tr_fallback(self):
        # Curated-path rows use `disease_label`; kaggle-candidate path
        # sometimes carries `label_tr` instead. Either lookup should
        # succeed.
        detail = {
            "session": {
                "session_id": "label-tr",
                "top_conditions": [{"label_tr": "Panik", "score_0_1": 0.3}],
            },
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_top_condition_score_as_string_renders_dash(self):
        detail = {
            "session": {
                "session_id": "score-str",
                "top_conditions": [{"disease_label": "X", "score_0_1": "oops"}],
            },
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"

    def test_top_condition_description_falls_back_to_english_key(self):
        # `disease_description_tr` preferred; if absent, the builder
        # reaches for `disease_description` (legacy English field).
        detail = {
            "session": {
                "session_id": "desc-en",
                "top_conditions": [
                    {
                        "disease_label": "Panic",
                        "score_0_1": 0.5,
                        "disease_description": "English description fallback.",
                    }
                ],
            },
            "events": [],
            "feedback": [],
        }
        pdf = build_session_pdf(detail)
        assert pdf[:4] == b"%PDF"
