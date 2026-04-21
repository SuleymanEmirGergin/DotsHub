"""Unit tests for app.explainability.build_explanation_trace.

The function is a pure accumulator: it appends Turkish summary lines
based on which inputs are truthy / non-None. No I/O, no side effects.
"""

from __future__ import annotations

import unittest

from app.explainability import build_explanation_trace


class BuildExplanationTraceTests(unittest.TestCase):
    # ---------- canonicals ----------

    def test_includes_canonicals_when_present(self):
        out = build_explanation_trace(
            extracted_canonicals=["a", "b"],
            confidence_0_1=0.5,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertTrue(
            any("Tespit edilen belirtiler" in s and "a, b" in s for s in out["summary"])
        )

    def test_canonicals_are_truncated_to_six(self):
        out = build_explanation_trace(
            extracted_canonicals=["c1", "c2", "c3", "c4", "c5", "c6", "c7"],
            confidence_0_1=0.1,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile=None,
        )
        line = next(s for s in out["summary"] if s.startswith("Tespit edilen"))
        self.assertIn("c1, c2, c3, c4, c5, c6", line)
        self.assertNotIn("c7", line)

    def test_empty_canonicals_list_is_skipped(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.7,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertFalse(
            any("Tespit edilen belirtiler" in s for s in out["summary"])
        )

    # ---------- confidence ----------

    def test_confidence_is_always_included_and_rounded(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.789,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertIn("Guven skoru: 0.79", out["summary"])

    def test_confidence_zero_when_none_like(self):
        # `confidence_0_1 or 0.0` handles falsy cases.
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertIn("Guven skoru: 0.0", out["summary"])

    # ---------- stop_reason ----------

    def test_stop_reason_included_when_truthy(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason="confident_top_specialty",
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertTrue(
            any("Durdurma nedeni: confident_top_specialty" in s for s in out["summary"])
        )

    def test_stop_reason_skipped_when_empty_string(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason="",
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertFalse(
            any("Durdurma nedeni" in s for s in out["summary"])
        )

    # ---------- same_day ----------

    def test_same_day_line_added_when_truthy_dict(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day={"suggest": True},
            duration_days=None,
            profile=None,
        )
        self.assertIn("Same-day kontrol onerisi aktif", out["summary"])

    def test_same_day_skipped_when_empty_dict(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day={},
            duration_days=None,
            profile=None,
        )
        self.assertNotIn("Same-day kontrol onerisi aktif", out["summary"])

    # ---------- duration_days ----------

    def test_duration_days_included_when_set(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=3,
            profile=None,
        )
        self.assertIn("Semptom suresi: 3 gun", out["summary"])

    def test_duration_days_zero_is_still_included(self):
        # `is not None` check, so 0 renders.
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=0,
            profile=None,
        )
        self.assertIn("Semptom suresi: 0 gun", out["summary"])

    def test_duration_days_none_is_skipped(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile=None,
        )
        self.assertFalse(any("Semptom suresi" in s for s in out["summary"]))

    # ---------- profile ----------

    def test_profile_with_age_only(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile={"age": 34},
        )
        self.assertTrue(any("Profil: yas 34" == s for s in out["summary"]))

    def test_profile_with_pregnant_only(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile={"pregnant": True},
        )
        self.assertTrue(any("Profil: gebelik" == s for s in out["summary"]))

    def test_profile_with_age_and_pregnant(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile={"age": 29, "pregnant": True},
        )
        self.assertTrue(
            any("Profil: yas 29, gebelik" == s for s in out["summary"])
        )

    def test_profile_with_non_int_age_is_skipped(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile={"age": "34"},  # str, not int
        )
        self.assertFalse(any("Profil" in s for s in out["summary"]))

    def test_profile_with_pregnant_false_is_skipped(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile={"pregnant": False},
        )
        self.assertFalse(any("Profil" in s for s in out["summary"]))

    def test_profile_empty_dict_adds_nothing(self):
        out = build_explanation_trace(
            extracted_canonicals=[],
            confidence_0_1=0.0,
            stop_reason=None,
            same_day=None,
            duration_days=None,
            profile={},
        )
        self.assertFalse(any("Profil" in s for s in out["summary"]))

    # ---------- combined / return shape ----------

    def test_return_shape_is_summary_list(self):
        out = build_explanation_trace(
            extracted_canonicals=["x"],
            confidence_0_1=0.8,
            stop_reason="top_specialty_confident",
            same_day={"a": 1},
            duration_days=5,
            profile={"age": 22, "pregnant": True},
        )
        self.assertEqual(set(out.keys()), {"summary"})
        self.assertIsInstance(out["summary"], list)
        # All 5 lines + confidence = 6 entries expected.
        self.assertEqual(len(out["summary"]), 6)


if __name__ == "__main__":
    unittest.main()
