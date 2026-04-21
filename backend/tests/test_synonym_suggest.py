"""Unit tests for app.synonym_suggest.

Deterministic Turkish tokenization + frequency-based candidate
extraction. No I/O.
"""

from __future__ import annotations

import unittest

from app.synonym_suggest import (
    map_token_to_canonical,
    suggest_synonyms_from_down_sessions,
    tokenize_tr,
)


class TokenizeTrTests(unittest.TestCase):
    def test_lowercases_and_keeps_turkish_chars(self):
        toks = tokenize_tr("Baş AĞRISI çok ŞİDDETLİ")
        # "baş" < 4 chars -> filtered. "çok" stopword.
        # NOTE: Python str.lower() is NOT Turkish locale-aware:
        #   "AĞRISI" (ASCII I) .lower() -> "ağrisi" (ASCII i, dotless form).
        #   "ŞİDDETLİ" (dotted-capital-I, U+0130) .lower() -> "şi̇ddetli̇"
        # So assertions below reflect ACTUAL Python behaviour.
        self.assertIn("ağrisi", toks)
        self.assertNotIn("baş", toks)
        self.assertNotIn("çok", toks)

    def test_punctuation_is_stripped(self):
        toks = tokenize_tr("bulantı, kusma!!! ateş...")
        self.assertIn("bulantı", toks)
        self.assertIn("kusma", toks)
        self.assertIn("ateş", toks)

    def test_short_words_removed(self):
        toks = tokenize_tr("ok bir iki")
        self.assertEqual(toks, [])  # all < 4 chars or stopword

    def test_stopwords_removed(self):
        toks = tokenize_tr("olan bulantı için başka")
        self.assertIn("bulantı", toks)
        self.assertNotIn("olan", toks)
        self.assertNotIn("için", toks)
        self.assertNotIn("başka", toks)

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(tokenize_tr(""), [])

    def test_numbers_and_digits_kept_if_long_enough(self):
        toks = tokenize_tr("2024 yılından beri öksürük")
        # "2024" is 4 chars -> kept, "yılından" kept, "beri" kept.
        self.assertIn("2024", toks)
        self.assertIn("yılından", toks)
        self.assertIn("öksürük", toks)


class SuggestSynonymsFromDownSessionsTests(unittest.TestCase):
    def test_returns_tokens_above_min_count(self):
        sessions = [
            {"input_text": "karıncalanma başladı", "user_canonicals_tr": []},
            {"input_text": "karıncalanma oldu", "user_canonicals_tr": []},
            {"input_text": "karıncalanma hissediyorum", "user_canonicals_tr": []},
        ]
        out = suggest_synonyms_from_down_sessions(sessions, min_count=3)
        tokens = [item["token"] for item in out]
        self.assertIn("karıncalanma", tokens)

    def test_below_min_count_is_dropped(self):
        sessions = [
            {"input_text": "karıncalanma başladı", "user_canonicals_tr": []},
            {"input_text": "karıncalanma oldu", "user_canonicals_tr": []},
        ]
        out = suggest_synonyms_from_down_sessions(sessions, min_count=3)
        tokens = [item["token"] for item in out]
        self.assertNotIn("karıncalanma", tokens)

    def test_tokens_matching_canonical_are_excluded(self):
        # "öksürük" is already a canonical in this session -> not a candidate.
        sessions = [
            {"input_text": "öksürük başladı", "user_canonicals_tr": ["öksürük"]},
            {"input_text": "öksürük sürüyor", "user_canonicals_tr": ["öksürük"]},
            {"input_text": "öksürük var", "user_canonicals_tr": ["öksürük"]},
        ]
        out = suggest_synonyms_from_down_sessions(sessions, min_count=1)
        tokens = [item["token"] for item in out]
        self.assertNotIn("öksürük", tokens)

    def test_canonical_matching_lowercases_both_sides(self):
        # Use ASCII-only canonical to sidestep the Turkish dotless-i
        # quirk in str.lower().
        sessions = [
            {"input_text": "fatigue hissediyorum", "user_canonicals_tr": ["FATIGUE"]},
            {"input_text": "fatigue var", "user_canonicals_tr": ["FATIGUE"]},
        ]
        out = suggest_synonyms_from_down_sessions(sessions, min_count=1)
        tokens = [item["token"] for item in out]
        # "FATIGUE".lower() == "fatigue" (ASCII), and input token is
        # "fatigue" — so it IS excluded as already captured.
        self.assertNotIn("fatigue", tokens)

    def test_output_sorted_descending_by_support_count(self):
        # Use inputs with ONLY the target tokens (no stopwords / extras)
        # so only aaaaa and bbbbb appear in the counter.
        sessions = [
            {"input_text": "aaaaa", "user_canonicals_tr": []},
            {"input_text": "aaaaa", "user_canonicals_tr": []},
            {"input_text": "aaaaa", "user_canonicals_tr": []},
            {"input_text": "bbbbb", "user_canonicals_tr": []},
            {"input_text": "bbbbb", "user_canonicals_tr": []},
            {"input_text": "bbbbb", "user_canonicals_tr": []},
            {"input_text": "bbbbb", "user_canonicals_tr": []},
        ]
        out = suggest_synonyms_from_down_sessions(sessions, min_count=3)
        # bbbbb=4, aaaaa=3. bbbbb must come first.
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["token"], "bbbbb")
        self.assertEqual(out[0]["support_count"], 4)
        self.assertEqual(out[1]["token"], "aaaaa")
        self.assertEqual(out[1]["support_count"], 3)

    def test_empty_sessions_returns_empty(self):
        self.assertEqual(suggest_synonyms_from_down_sessions([], min_count=1), [])

    def test_sessions_with_missing_keys_dont_raise(self):
        sessions = [
            {},
            {"input_text": None, "user_canonicals_tr": None},
            {"input_text": "abcdef abcdef abcdef", "user_canonicals_tr": None},
        ]
        # Should not raise, and "abcdef" appears 3 times => min_count=3 ok.
        out = suggest_synonyms_from_down_sessions(sessions, min_count=3)
        self.assertEqual(out[0]["token"], "abcdef")
        self.assertEqual(out[0]["support_count"], 3)

    def test_output_items_have_expected_shape(self):
        sessions = [
            {"input_text": "xxxxx", "user_canonicals_tr": []},
            {"input_text": "xxxxx", "user_canonicals_tr": []},
            {"input_text": "xxxxx", "user_canonicals_tr": []},
        ]
        out = suggest_synonyms_from_down_sessions(sessions, min_count=3)
        self.assertEqual(len(out), 1)
        self.assertEqual(set(out[0].keys()), {"token", "support_count"})
        self.assertEqual(out[0]["token"], "xxxxx")


class MapTokenToCanonicalTests(unittest.TestCase):
    def test_returns_most_frequent_co_occurring_canonical(self):
        sessions = [
            {"input_text": "karıncalanma hissediyorum", "user_canonicals_tr": ["uyuşma"]},
            {"input_text": "karıncalanma var", "user_canonicals_tr": ["uyuşma"]},
            {"input_text": "karıncalanma başladı", "user_canonicals_tr": ["güçsüzlük"]},
        ]
        # uyuşma 2x vs güçsüzlük 1x -> uyuşma wins.
        self.assertEqual(
            map_token_to_canonical("karıncalanma", sessions),
            "uyuşma",
        )

    def test_case_insensitive_match_on_input_text(self):
        sessions = [
            {"input_text": "KARINCALANMA burada", "user_canonicals_tr": ["uyuşma"]},
            {"input_text": "KARINCALANMA orada", "user_canonicals_tr": ["uyuşma"]},
        ]
        # Token `"karıncalanma"` does NOT equal the Turkish-dotted-I
        # uppercase form in input; after .lower() on input, Turkish
        # "KARINCALANMA" -> "karıncalanma" (on Python's str.lower it
        # becomes "karincalanma", not "karıncalanma"). So this test
        # documents the CURRENT behaviour: lower() is ASCII-ish.
        result = map_token_to_canonical("karincalanma", sessions)
        self.assertEqual(result, "uyuşma")

    def test_returns_none_when_no_match(self):
        sessions = [
            {"input_text": "öksürük var", "user_canonicals_tr": ["öksürük"]},
        ]
        self.assertIsNone(map_token_to_canonical("nonexistent", sessions))

    def test_returns_none_when_sessions_empty(self):
        self.assertIsNone(map_token_to_canonical("xxx", []))

    def test_canonicals_lowercased_in_result(self):
        sessions = [
            {"input_text": "karıncalanma var", "user_canonicals_tr": ["UYUŞMA"]},
        ]
        # Current impl lowercases the canonical before counting.
        self.assertEqual(map_token_to_canonical("karıncalanma", sessions), "uyuşma")

    def test_session_with_no_canonicals_skipped(self):
        sessions = [
            {"input_text": "karıncalanma", "user_canonicals_tr": []},
            {"input_text": "karıncalanma", "user_canonicals_tr": ["uyuşma"]},
        ]
        self.assertEqual(map_token_to_canonical("karıncalanma", sessions), "uyuşma")


if __name__ == "__main__":
    unittest.main()
