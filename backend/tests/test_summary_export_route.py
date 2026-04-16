from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import rate_limit
from app.api.routes import summary_email as summary_email_routes
from app.main import app


class _SendSummaryRateLimitIsolationTestCase(unittest.TestCase):
    """Prevent cross-test pollution from in-memory send-summary buckets."""

    def setUp(self):
        rate_limit._SEND_SUMMARY_BUCKETS.clear()

    def tearDown(self):
        rate_limit._SEND_SUMMARY_BUCKETS.clear()


class SummaryExportRouteTests(_SendSummaryRateLimitIsolationTestCase):
    def test_export_summary_returns_plain_text(self):
        payload = {
            "recommended_specialty": {"id": "internal", "name_tr": "Dahiliye"},
            "doctor_ready_summary_tr": ["Ornek satir"],
        }

        with (
            patch.object(summary_email_routes, "build_export_text", return_value="exported") as mocked_export,
            TestClient(app) as client,
        ):
            response = client.post(
                "/v1/triage/export-summary",
                json={"payload": payload, "locale": "en"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "exported")
        self.assertIn("text/plain", response.headers.get("content-type", ""))
        mocked_export.assert_called_once_with(payload, locale="en")


class SendSummaryRouteTests(_SendSummaryRateLimitIsolationTestCase):
    def test_send_summary_404_when_session_not_found(self):
        with (
            patch.object(summary_email_routes, "_get_session_by_id", return_value=None),
            TestClient(app) as client,
        ):
            response = client.post(
                "/v1/triage/send-summary",
                json={
                    "session_id": "00000000-0000-0000-0000-000000000001",
                    "email": "test@example.com",
                    "locale": "tr",
                },
            )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Session not found", response.json().get("detail", ""))

    def test_send_summary_200_when_session_found(self):
        fake_session = {
            "id": "00000000-0000-0000-0000-000000000001",
            "recommended_specialty_tr": "Dahiliye",
            "confidence_label_tr": "Yüksek",
            "stop_reason": "enough_signal",
            "created_at": "2024-01-01T12:00:00Z",
        }
        with (
            patch.object(summary_email_routes, "_get_session_by_id", return_value=fake_session),
            patch.object(summary_email_routes, "send_session_summary_email") as mock_send,
            TestClient(app) as client,
        ):
            response = client.post(
                "/v1/triage/send-summary",
                json={
                    "session_id": fake_session["id"],
                    "email": "user@example.com",
                    "locale": "tr",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "message": "Summary email sent or queued"})
        mock_send.assert_called_once()
        call_kw = mock_send.call_args[1]
        self.assertEqual(call_kw["locale"], "tr")

    def test_send_summary_422_invalid_email(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/send-summary",
                json={
                    "session_id": "00000000-0000-0000-0000-000000000001",
                    "email": "not-an-email",
                    "locale": "tr",
                },
            )
        self.assertEqual(response.status_code, 422)

    def test_send_summary_422_missing_session_id(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/send-summary",
                json={
                    "email": "user@example.com",
                    "locale": "tr",
                },
            )
        self.assertEqual(response.status_code, 422)


class ExportSummaryValidationTests(_SendSummaryRateLimitIsolationTestCase):
    def test_export_summary_422_missing_payload(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/export-summary",
                json={"locale": "en"},
            )
        self.assertEqual(response.status_code, 422)


class ExportSummaryIntegrationTests(_SendSummaryRateLimitIsolationTestCase):
    """Integration: export-summary route with real build_export_text for different locales."""

    def test_export_summary_200_locale_tr_returns_plain_text(self):
        payload = {
            "recommended_specialty": {"id": "internal", "name_tr": "Dahiliye"},
            "doctor_ready_summary_tr": ["Özet satırı"],
        }
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/export-summary",
                json={"payload": payload, "locale": "tr-TR"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("content-type", ""))
        self.assertIn("Triaj oturum özeti", response.text)
        self.assertIn("Dahiliye", response.text)

    def test_export_summary_200_locale_en_returns_english_headers(self):
        payload = {
            "recommended_specialty": {"id": "internal", "name_tr": "Internal Medicine"},
            "doctor_ready_summary_tr": ["Summary line"],
        }
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/export-summary",
                json={"payload": payload, "locale": "en"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("content-type", ""))
        self.assertIn("Triage session summary", response.text)
        self.assertIn("Recommended specialty", response.text)

    def test_export_summary_200_locale_de_falls_back_to_turkish_content(self):
        payload = {"recommended_specialty": {"name_tr": "Dahiliye"}}
        with TestClient(app) as client:
            response = client.post(
                "/v1/triage/export-summary",
                json={"payload": payload, "locale": "de"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("content-type", ""))
        self.assertIn("Triaj oturum özeti", response.text)


class SendSummaryRateLimitTests(_SendSummaryRateLimitIsolationTestCase):
    """send-summary rate limit: SEND_SUMMARY_MAX_REQ (default 5) per minute per IP."""

    def test_send_summary_429_after_limit_exceeded(self):
        fake_session = {
            "id": "00000000-0000-0000-0000-000000000001",
            "recommended_specialty_tr": "Dahiliye",
            "confidence_label_tr": "Yüksek",
            "stop_reason": "enough_signal",
            "created_at": "2024-01-01T12:00:00Z",
        }
        with (
            patch.object(summary_email_routes, "_get_session_by_id", return_value=fake_session),
            patch.object(summary_email_routes, "send_session_summary_email"),
            TestClient(app) as client,
        ):
            # Exhaust limit (default 5)
            for i in range(6):
                response = client.post(
                    "/v1/triage/send-summary",
                    json={
                        "session_id": fake_session["id"],
                        "email": f"user{i}@example.com",
                        "locale": "tr",
                    },
                )
                if i < 5:
                    self.assertEqual(response.status_code, 200, f"request {i + 1} should be 200")
                else:
                    self.assertEqual(response.status_code, 429, "6th request should be rate limited")
                    self.assertIn("Rate limit exceeded", response.json().get("detail", ""))

    def test_export_summary_429_after_limit_exceeded(self):
        """export-summary shares the same 5/min bucket; 6th request returns 429 with X-RateLimit-* headers."""
        payload = {
            "recommended_specialty": {"id": "internal", "name_tr": "Dahiliye"},
            "doctor_ready_summary_tr": ["Line"],
        }
        with (
            patch.object(summary_email_routes, "build_export_text", return_value="exported"),
            TestClient(app) as client,
        ):
            for i in range(6):
                response = client.post(
                    "/v1/triage/export-summary",
                    json={"payload": payload, "locale": "en"},
                )
                if i < 5:
                    self.assertEqual(response.status_code, 200, f"request {i + 1} should be 200")
                    self.assertIn("X-RateLimit-Limit", response.headers)
                    self.assertIn("X-RateLimit-Remaining", response.headers)
                else:
                    self.assertEqual(response.status_code, 429, "6th request should be rate limited")
                    self.assertIn("Rate limit exceeded", response.json().get("detail", ""))
                    self.assertEqual(response.headers.get("X-RateLimit-Remaining"), "0")


if __name__ == "__main__":
    unittest.main()
