"""Unit tests for canonical_extract.py — pure-function coverage.

Covers the two uncovered branches surfaced by coverage audit (lines 49
and 66: empty-canonical skip and dedup skip in build_synonym_patterns)
plus enough happy-path and edge-case tests to guard against regression.

Companion to the integration coverage from test_triage_engine_regression
and test_golden_flows — those tests exercise the module end-to-end but
don't hit the guard clauses that matter when the synonyms JSON is
partially malformed (empty canonical string, duplicate variants).
"""

from __future__ import annotations

import unittest

from app.canonical_extract import (
    build_synonym_patterns,
    extract_canonicals_tr,
    is_negated,
    normalize_text_tr,
    tr_lower,
)


class TrLowerTests(unittest.TestCase):
    def test_turkish_capital_i_with_dot_becomes_lowercase_i(self):
        self.assertEqual(tr_lower("İSTANBUL"), "istanbul")

    def test_turkish_capital_i_without_dot_becomes_dotless_i(self):
        self.assertEqual(tr_lower("IŞIK"), "ışık")

    def test_ascii_letters_lowercase_normally(self):
        self.assertEqual(tr_lower("HELLO"), "hello")

    def test_empty_string_passthrough(self):
        self.assertEqual(tr_lower(""), "")


class NormalizeTextTrTests(unittest.TestCase):
    def test_lowercases_turkish(self):
        self.assertIn("istanbul", normalize_text_tr("İSTANBUL"))

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_text_tr("  a   b  "), "a b")

    def test_empty_string_passthrough(self):
        self.assertEqual(normalize_text_tr(""), "")


class BuildSynonymPatternsTests(unittest.TestCase):
    def test_empty_synonyms_returns_empty_list(self):
        self.assertEqual(build_synonym_patterns({}), [])
        self.assertEqual(build_synonym_patterns({"synonyms": []}), [])

    def test_skips_entry_with_empty_canonical(self):
        """Line 49 coverage: entries with blank canonical are skipped
        rather than producing spurious empty patterns.
        """
        out = build_synonym_patterns(
            {
                "synonyms": [
                    {"canonical": "", "variants_tr": ["foo"]},
                    {"canonical": "ateş", "variants_tr": ["yüksek ateş"]},
                ]
            }
        )
        # Only "ateş" survived — the blank-canonical entry was dropped
        canonicals = {c for c, _ in out}
        self.assertEqual(canonicals, {"ateş"})

    def test_dedupes_duplicate_canonical_phrase_pairs(self):
        """Line 66 coverage: when two entries yield the same
        canonical|phrase key, only the first is kept.
        """
        out = build_synonym_patterns(
            {
                "synonyms": [
                    {"canonical": "ateş", "variants_tr": ["yüksek ateş", "yüksek ateş"]},
                ]
            }
        )
        # Three expected entries without dedup: canonical itself + 2x variant.
        # With dedup, only canonical + 1x variant survive.
        self.assertEqual(len(out), 2)

    def test_canonical_itself_is_included_as_a_phrase(self):
        out = build_synonym_patterns(
            {"synonyms": [{"canonical": "ateş", "variants_tr": []}]}
        )
        self.assertEqual(len(out), 1)
        canonical, pat = out[0]
        self.assertEqual(canonical, "ateş")
        self.assertRegex("ateş", pat)

    def test_sorted_longest_phrase_first(self):
        out = build_synonym_patterns(
            {
                "synonyms": [
                    {"canonical": "baş ağrısı", "variants_tr": ["baş", "başım çok ağrıyor"]},
                ]
            }
        )
        # Compiled pattern escapes spaces, so match on actual text
        # rather than the raw pattern string.
        self.assertRegex("başım çok ağrıyor", out[0][1])


class IsNegatedTests(unittest.TestCase):
    def test_detects_negation_within_window(self):
        text = "yok ateş"  # "yok" within 3-word window before "ateş"
        self.assertTrue(is_negated(text, start_idx=4, negations=["yok"], window=20))

    def test_no_negation_returns_false(self):
        text = "var ateş"
        self.assertFalse(is_negated(text, start_idx=4, negations=["yok"], window=20))

    def test_empty_negations_returns_false(self):
        self.assertFalse(is_negated("yok ateş", start_idx=4, negations=[], window=20))


class ExtractCanonicalsTrTests(unittest.TestCase):
    _SYN = {
        "synonyms": [
            {"canonical": "ateş", "variants_tr": ["ateşim var", "yüksek ateş"]},
            {"canonical": "baş ağrısı", "variants_tr": ["başım ağrıyor"]},
        ]
    }

    def test_extracts_single_canonical(self):
        out = extract_canonicals_tr(
            text_tr="ateşim var", answers={}, synonyms_json=self._SYN
        )
        self.assertIn("ateş", out)

    def test_extracts_multiple_canonicals(self):
        out = extract_canonicals_tr(
            text_tr="başım ağrıyor ve ateşim var",
            answers={},
            synonyms_json=self._SYN,
        )
        self.assertIn("ateş", out)
        self.assertIn("baş ağrısı", out)

    def test_empty_text_returns_empty(self):
        out = extract_canonicals_tr(text_tr="", answers={}, synonyms_json=self._SYN)
        self.assertEqual(out, [])

    def test_unknown_text_returns_empty(self):
        out = extract_canonicals_tr(
            text_tr="bu tamamen alakasiz bir cumle",
            answers={},
            synonyms_json=self._SYN,
        )
        self.assertEqual(out, [])

    def test_negation_drops_match(self):
        """Line 112 coverage: negated match is skipped via `continue`.

        is_negated scans the window BEFORE the match, so the negation
        token has to precede the phrase. "yok" within 18 chars before
        "ateş" should suppress the match.
        """
        syn = {"synonyms": [{"canonical": "ateş", "variants_tr": ["ateş"]}]}
        out = extract_canonicals_tr(
            text_tr="yok ateş", answers={}, synonyms_json=syn
        )
        self.assertNotIn("ateş", out)

    def test_answers_contribute_canonicals(self):
        """Lines 117-120 coverage: answer keys are added as canonicals."""
        out = extract_canonicals_tr(
            text_tr="",
            answers={"çarpıntı": "yes", "": "ignored_empty"},
            synonyms_json={"synonyms": []},
        )
        self.assertIn("çarpıntı", out)


if __name__ == "__main__":
    unittest.main()
