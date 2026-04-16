"""Unit tests for app.services.email_summary.build_summary_body."""

from __future__ import annotations

import unittest

from app.services.email_summary import build_summary_body


class BuildSummaryBodyTests(unittest.TestCase):
    def test_tr_locale_produces_turkish_title_and_lines(self):
        session = {
            "id": "sess-123",
            "recommended_specialty_tr": "Dahiliye",
            "confidence_label_tr": "Yüksek",
            "stop_reason": "enough_signal",
            "created_at": "2024-01-01T12:00:00Z",
        }
        text, html = build_summary_body(session, locale="tr")
        self.assertIn("Ön Triage oturum özeti", text)
        self.assertIn("Oturum ID", text)
        self.assertIn("sess-123", text)
        self.assertIn("Önerilen branş", text)
        self.assertIn("Dahiliye", text)
        self.assertIn("<h2>", html)
        self.assertIn("Ön Triage oturum özeti", html)

    def test_en_locale_produces_english_title_and_lines(self):
        session = {
            "id": "sess-456",
            "recommended_specialty_tr": "Internal Medicine",
            "confidence_label_tr": "High",
            "stop_reason": "enough_signal",
            "created_at": "2024-01-02T10:00:00Z",
        }
        text, html = build_summary_body(session, locale="en")
        self.assertIn("Pre-Triage session summary", text)
        self.assertIn("Session ID", text)
        self.assertIn("sess-456", text)
        self.assertIn("Recommended specialty", text)
        self.assertIn("Internal Medicine", text)
        self.assertIn("Pre-Triage session summary", html)

    def test_minimal_session_uses_defaults(self):
        session = {}
        text, html = build_summary_body(session, locale="tr")
        self.assertIn("Ön Triage oturum özeti", text)
        self.assertIn("Oturum ID", text)
        self.assertIn("-", text)
        self.assertIn("<pre>", html)
