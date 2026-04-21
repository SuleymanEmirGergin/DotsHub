"""Unit tests for app.free_text_parse.

Parses user free-text answers into structured fields:
  - duration_days: "3 gündür" -> 3
  - severity_0_10: "çok kötü" or "7/10" -> 1-10
  - timing: "sabah kalkınca" -> "sabah"
"""

from __future__ import annotations

import unittest

from app.free_text_parse import (
    parse_duration,
    parse_free_text_answer,
    parse_severity,
    parse_timing,
    parsed_to_symptom_item,
)


class ParseDurationTests(unittest.TestCase):
    def test_parses_days_from_turkish_text(self):
        self.assertEqual(parse_duration("3 gündür"), 3)

    def test_parses_weeks_as_days(self):
        # extract_duration_days converts weeks to days.
        self.assertEqual(parse_duration("2 haftadır"), 14)

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_duration(""))

    def test_none_returns_none(self):
        # The `or ""` guard means a falsy input falls through to extract_duration_days("")
        self.assertIsNone(parse_duration(None))  # type: ignore[arg-type]

    def test_text_without_duration_returns_none(self):
        self.assertIsNone(parse_duration("ağrıyor"))


class ParseSeverityTests(unittest.TestCase):
    def test_numeric_7_out_of_10(self):
        self.assertEqual(parse_severity("7/10"), 7.0)

    def test_numeric_bare_integer(self):
        self.assertEqual(parse_severity("8"), 8.0)

    def test_numeric_single_digit_out_of_10(self):
        # "3 üzerinden 10" or "3/10"
        self.assertEqual(parse_severity("3/10"), 3.0)

    def test_verbal_very_severe(self):
        self.assertEqual(parse_severity("çok şiddetli ağrı"), 9.0)

    def test_verbal_severe(self):
        self.assertEqual(parse_severity("şiddetli ağrı"), 8.0)

    def test_verbal_moderate(self):
        self.assertEqual(parse_severity("orta şiddette"), 6.0)

    def test_verbal_mild(self):
        self.assertEqual(parse_severity("hafif ağrı"), 2.0)

    def test_none_returns_none(self):
        self.assertIsNone(parse_severity(None))  # type: ignore[arg-type]

    def test_non_string_returns_none(self):
        self.assertIsNone(parse_severity(5))  # type: ignore[arg-type]

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_severity(""))

    def test_unparseable_text_returns_none(self):
        # Use text without any digits or verbal severity substrings
        # ("hafif", "az", "biraz", "şiddetli", "orta", "kötü", etc).
        self.assertIsNone(parse_severity("ağrıyor sürekli"))

    def test_parses_uzeringen_10_scale(self):
        # Covers the second regex branch (line 80-87).
        self.assertEqual(parse_severity("7 üzerinden 10"), 7.0)

    def test_parses_with_dash_separator(self):
        # Covers the `[\s\-]` branch of the second regex.
        self.assertEqual(parse_severity("7-10"), 7.0)


class ParseTimingTests(unittest.TestCase):
    def test_sabah_keyword(self):
        self.assertEqual(parse_timing("sabah kalkınca oldu"), "sabah")

    def test_kalkınca_variant(self):
        self.assertEqual(parse_timing("kalktığımda"), "sabah")

    def test_akşam(self):
        self.assertEqual(parse_timing("akşamleyin"), "akşam")

    def test_gece_variants(self):
        self.assertEqual(parse_timing("yatarken"), "gece")
        self.assertEqual(parse_timing("uyurken"), "gece")
        self.assertEqual(parse_timing("geceleri"), "gece")

    def test_gündüz(self):
        self.assertEqual(parse_timing("gün boyu"), "gündüz")

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_timing(""))

    def test_none_returns_none(self):
        self.assertIsNone(parse_timing(None))  # type: ignore[arg-type]

    def test_non_string_returns_none(self):
        self.assertIsNone(parse_timing(123))  # type: ignore[arg-type]

    def test_no_timing_keyword_returns_none(self):
        self.assertIsNone(parse_timing("sürekli ağrı"))


class ParseFreeTextAnswerTests(unittest.TestCase):
    def test_duration_canonical_parses_duration(self):
        out = parse_free_text_answer("öksürük süresi", "3 gündür")
        self.assertEqual(out, {"duration_days": 3})

    def test_severity_canonical_parses_severity(self):
        out = parse_free_text_answer("ağrı şiddeti", "7/10")
        self.assertEqual(out, {"severity_0_10": 7.0})

    def test_timing_canonical_parses_timing(self):
        out = parse_free_text_answer("baş ağrısı sabah artışı", "sabah kalkınca oluyor")
        self.assertEqual(out, {"timing": "sabah"})

    def test_duration_canonical_with_timing_info_captures_both(self):
        # "öksürük süresi" is in both DURATION_CANONICALS and TIMING_CANONICALS.
        out = parse_free_text_answer("öksürük süresi", "3 gündür, geceleri oluyor")
        self.assertEqual(out.get("duration_days"), 3)
        self.assertEqual(out.get("timing"), "gece")

    def test_empty_canonical_returns_empty_dict(self):
        self.assertEqual(parse_free_text_answer("", "something"), {})

    def test_empty_raw_value_returns_empty_dict(self):
        self.assertEqual(parse_free_text_answer("öksürük süresi", ""), {})

    def test_whitespace_only_raw_returns_empty_dict(self):
        self.assertEqual(parse_free_text_answer("öksürük süresi", "   "), {})

    def test_unknown_canonical_returns_empty_dict(self):
        self.assertEqual(
            parse_free_text_answer("bilinmeyen_kanonik", "3 gündür"),
            {},
        )

    def test_duration_canonical_with_unparseable_raw_empty(self):
        self.assertEqual(parse_free_text_answer("öksürük süresi", "xxx"), {})


class ParsedToSymptomItemTests(unittest.TestCase):
    def test_empty_parsed_returns_none(self):
        self.assertIsNone(parsed_to_symptom_item("öksürük süresi", {}))

    def test_parsed_with_only_duration(self):
        out = parsed_to_symptom_item("öksürük süresi", {"duration_days": 5})
        self.assertEqual(out, {"name_tr": "öksürük süresi", "duration_tr": "5 gün"})

    def test_parsed_with_only_severity(self):
        out = parsed_to_symptom_item("ağrı şiddeti", {"severity_0_10": 8.0})
        self.assertEqual(
            out,
            {"name_tr": "ağrı şiddeti", "severity_0_10": 8.0},
        )

    def test_parsed_with_both_duration_and_severity(self):
        out = parsed_to_symptom_item(
            "öksürük süresi",
            {"duration_days": 3, "severity_0_10": 6.0},
        )
        assert out is not None
        self.assertEqual(out["name_tr"], "öksürük süresi")
        self.assertEqual(out["duration_tr"], "3 gün")
        self.assertEqual(out["severity_0_10"], 6.0)

    def test_parsed_with_only_timing_returns_none(self):
        # Timing alone doesn't upgrade the symptom_item (len <= 1 after timing stripped).
        out = parsed_to_symptom_item(
            "öksürük süresi",
            {"timing": "sabah"},
        )
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
