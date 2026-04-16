"""Unit tests for app.services.export_summary.build_export_text."""

from __future__ import annotations

import unittest

from app.services.export_summary import build_export_text


class BuildExportTextTests(unittest.TestCase):
    def test_turkish_locale_produces_turkish_headers(self):
        payload = {
            "recommended_specialty": {"id": "internal", "name_tr": "Dahiliye"},
            "urgency": "ROUTINE",
            "doctor_ready_summary_tr": ["Özet satırı"],
            "top_conditions": [{"disease_label": "Üriner enfeksiyon", "score_0_1": 0.8}],
            "safety_notes_tr": ["Bol sıvı alın."],
        }
        result = build_export_text(payload, locale="tr-TR")
        self.assertIn("Triaj oturum özeti", result)
        self.assertIn("Önerilen branş", result)
        self.assertIn("Dahiliye", result)
        self.assertIn("Aciliyet", result)
        self.assertIn("Uyarılar", result)
        self.assertIn("Bol sıvı alın", result)

    def test_english_locale_produces_english_headers(self):
        payload = {
            "recommended_specialty": {"id": "internal", "name_tr": "Internal Medicine"},
            "urgency": "ROUTINE",
            "doctor_ready_summary_tr": ["Summary line"],
            "top_conditions": [{"disease_label": "UTI", "score_0_1": 0.8}],
            "safety_notes_tr": ["Drink fluids."],
        }
        result = build_export_text(payload, locale="en")
        self.assertIn("Triage session summary", result)
        self.assertIn("Recommended specialty", result)
        self.assertIn("Safety notes", result)
        self.assertIn("Drink fluids", result)

    def test_empty_payload_does_not_crash(self):
        result = build_export_text({}, locale="tr-TR")
        self.assertIn("Triaj oturum özeti", result)
        self.assertIn("Önerilen branş", result)
        self.assertIsInstance(result, str)

    def test_de_locale_falls_back_to_turkish_content(self):
        payload = {"recommended_specialty": {"name_tr": "Dahiliye"}}
        result = build_export_text(payload, locale="de")
        self.assertIn("Triaj oturum özeti", result)
        self.assertIn("Önerilen branş", result)
