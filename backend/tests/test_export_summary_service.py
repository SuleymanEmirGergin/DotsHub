"""Unit tests for app.services.export_summary.build_export_text.

No HTTP, no mocks — pure function tests.
conftest.py sets the required env vars so app modules can be imported safely.
"""

from __future__ import annotations

import unittest

from app.services.export_summary import build_export_text


class BuildExportTextTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # 1. Empty payload must not raise and must fall back to Turkish header
    # ------------------------------------------------------------------
    def test_empty_payload_does_not_raise(self):
        result = build_export_text({})
        self.assertIn("Triaj oturum özeti", result)

    # ------------------------------------------------------------------
    # 2. recommended_specialty = None → dash
    # ------------------------------------------------------------------
    def test_null_specialty_uses_dash(self):
        result = build_export_text({"recommended_specialty": None})
        self.assertIn("Önerilen branş: -", result)

    # ------------------------------------------------------------------
    # 3. recommended_specialty key absent → dash
    # ------------------------------------------------------------------
    def test_missing_specialty_key_uses_dash(self):
        result = build_export_text({"urgency": "ROUTINE"})
        self.assertIn("-", result)

    # ------------------------------------------------------------------
    # 4. sentence field takes priority over list field
    # ------------------------------------------------------------------
    def test_sentence_field_takes_priority_over_list(self):
        payload = {
            "doctor_ready_summary_sentence_tr": "Sentence.",
            "doctor_ready_summary_tr": ["Line1"],
        }
        result = build_export_text(payload)
        self.assertIn("Sentence.", result)
        self.assertNotIn("Line1", result)

    # ------------------------------------------------------------------
    # 5. Empty top_conditions → no condition lines after header
    # ------------------------------------------------------------------
    def test_empty_top_conditions_produces_no_condition_lines(self):
        result = build_export_text({"top_conditions": []})
        # Must not crash; the section header exists but nothing follows it
        self.assertIn("Olası durumlar:", result)
        lines = result.splitlines()
        conditions_idx = next(
            i for i, line in enumerate(lines) if "Olası durumlar:" in line
        )
        # Lines after the header must contain no condition entries ("  - ...")
        remaining = lines[conditions_idx + 1:]
        condition_entries = [ln for ln in remaining if ln.startswith("  -")]
        self.assertEqual(condition_entries, [])

    # ------------------------------------------------------------------
    # 6. Empty safety_notes_tr → no crash
    # ------------------------------------------------------------------
    def test_empty_safety_notes_produces_no_note_lines(self):
        result = build_export_text({"safety_notes_tr": []})
        self.assertIn("Uyarılar:", result)
        lines = result.splitlines()
        notes_idx = next(i for i, line in enumerate(lines) if "Uyarılar:" in line)
        remaining = lines[notes_idx + 1:]
        note_entries = [ln for ln in remaining if ln.startswith("  -")]
        self.assertEqual(note_entries, [])

    # ------------------------------------------------------------------
    # 7. EN locale → English headers, no Turkish header
    # ------------------------------------------------------------------
    def test_en_locale_uses_english_headers(self):
        result = build_export_text({}, locale="en")
        self.assertIn("Triage session summary", result)
        self.assertNotIn("Triaj", result)

    # ------------------------------------------------------------------
    # 8. TR locale → Turkish headers
    # ------------------------------------------------------------------
    def test_tr_locale_uses_turkish_headers(self):
        result = build_export_text({}, locale="tr-TR")
        self.assertIn("Triaj oturum özeti", result)

    # ------------------------------------------------------------------
    # 9. urgency value appears in output
    # ------------------------------------------------------------------
    def test_urgency_appears_in_output(self):
        result = build_export_text({"urgency": "URGENT"})
        self.assertIn("URGENT", result)

    # ------------------------------------------------------------------
    # 10. Condition score renders as percentage in TR locale
    # ------------------------------------------------------------------
    def test_top_conditions_score_renders_as_percentage_in_tr(self):
        payload = {
            "top_conditions": [
                {"disease_label": "Migren", "score_0_1": 0.75}
            ]
        }
        result = build_export_text(payload, locale="tr-TR")
        self.assertIn("Migren", result)
        self.assertIn("%75", result)


if __name__ == "__main__":
    unittest.main()
