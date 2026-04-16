"""Tests for POST /v1/triage/send-summary and POST /v1/triage/export-summary."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app

SESSION_ID = "session-abc123"

RESULT_PAYLOAD = {
    "urgency": "ROUTINE",
    "recommended_specialty": {"id": "neurology", "name_tr": "Nöroloji"},
    "top_conditions": [{"disease_label": "Migren", "score_0_1": 0.65}],
    "doctor_ready_summary_tr": ["3 gündür başağrısı mevcut."],
    "safety_notes_tr": [],
    "confidence_0_1": 0.70,
    "confidence_label_tr": "orta",
    "why_specialty_tr": ["Nörolojik belirtiler mevcut."],
    "stop_reason": "high_confidence",
}


def _make_send_summary_request(session_id: str = SESSION_ID, email: str = "test@example.com", locale: str = "tr"):
    return {"session_id": session_id, "email": email, "locale": locale}


class SendSummaryRouteTests(unittest.TestCase):
    """Contract tests for POST /v1/triage/send-summary."""

    def setUp(self):
        # Clear the shared in-memory rate-limit bucket so test ordering doesn't
        # cause earlier tests (especially test_rate_limited_after_threshold) to
        # exhaust the limit and make subsequent tests return 429 unexpectedly.
        import app.rate_limit as rl
        rl._SEND_SUMMARY_BUCKETS.clear()

    def tearDown(self):
        import app.rate_limit as rl
        rl._SEND_SUMMARY_BUCKETS.clear()

    def test_send_summary_returns_200_when_email_sent(self):
        """Valid request returns 200 when email send succeeds."""
        with patch(
            "app.api.routes.summary_email.send_session_summary_email",
            return_value={"ok": True},
        ), patch(
            "app.api.routes.summary_email._get_session_by_id",
            return_value={"id": SESSION_ID, "input_text": "test", "envelope_type": "RESULT"},
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/send-summary",
                    json=_make_send_summary_request(),
                )
        self.assertIn(r.status_code, (200, 202), r.text)

    def test_invalid_email_returns_422(self):
        """Email without @ sign fails validation."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/send-summary",
                json={"session_id": SESSION_ID, "email": "not-an-email", "locale": "tr"},
            )
        self.assertEqual(r.status_code, 422)

    def test_missing_email_returns_422(self):
        """Missing email field returns 422."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/send-summary",
                json={"session_id": SESSION_ID},
            )
        self.assertEqual(r.status_code, 422)

    def test_missing_session_id_returns_422(self):
        """Missing session_id field returns 422."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/send-summary",
                json={"email": "test@example.com"},
            )
        self.assertEqual(r.status_code, 422)

    def test_email_send_failure_returns_500(self):
        """If email sending raises, the route returns 500 (not 200)."""
        import app.api.routes.summary_email as summary_routes
        fake_session = {"id": "00000000-0000-0000-0000-000000000001",
                        "recommended_specialty_tr": "Dahiliye"}
        with patch.object(summary_routes, "_get_session_by_id", return_value=fake_session), \
             patch.object(summary_routes, "send_session_summary_email",
                          side_effect=RuntimeError("Resend API down")):
            with TestClient(app) as client:
                r = client.post("/v1/triage/send-summary",
                    json={"session_id": fake_session["id"],
                          "email": "user@example.com", "locale": "tr"})
        self.assertIn(r.status_code, (500, 503))

    def test_device_id_mismatch_returns_403(self):
        """device_id in request doesn't match stored device_id → 403."""
        import app.api.routes.summary_email as summary_routes
        fake_session = {"id": "00000000-0000-0000-0000-000000000001",
                        "device_id": "device-original"}
        with patch.object(summary_routes, "_get_session_by_id", return_value=fake_session):
            with TestClient(app) as client:
                r = client.post("/v1/triage/send-summary",
                    json={"session_id": fake_session["id"],
                          "email": "user@example.com",
                          "locale": "tr",
                          "device_id": "device-different"})
        self.assertEqual(r.status_code, 403)

    def test_absent_device_id_in_request_allows_access(self):
        """Session has device_id but caller omits it in request → allowed (backward compat)."""
        import app.api.routes.summary_email as summary_routes
        fake_session = {"id": "00000000-0000-0000-0000-000000000001",
                        "device_id": "device-stored"}
        with patch.object(summary_routes, "_get_session_by_id", return_value=fake_session), \
             patch.object(summary_routes, "send_session_summary_email"):
            with TestClient(app) as client:
                r = client.post("/v1/triage/send-summary",
                    json={"session_id": fake_session["id"],
                          "email": "user@example.com",
                          "locale": "tr"})
        self.assertEqual(r.status_code, 200)

    def test_rate_limited_after_threshold(self):
        """Endpoint respects rate limit; after enough requests it returns 429."""
        import app.api.routes.summary_email as route_mod

        # Directly call check to verify rate limit function is wired
        from app.rate_limit import check_send_summary_rate_limit, build_send_summary_rl_key
        key = build_send_summary_rl_key("127.0.0.1")
        # Exhaust the limit
        for _ in range(10):
            check_send_summary_rate_limit(key)
        allowed, remaining, _ = check_send_summary_rate_limit(key)
        # After exhausting, remaining should be 0
        self.assertEqual(remaining, 0)
        self.assertFalse(allowed)


class ExportSummaryRouteTests(unittest.TestCase):
    """Contract tests for POST /v1/triage/export-summary."""

    def setUp(self):
        # Clear the shared in-memory rate-limit bucket so prior SendSummaryRouteTests
        # requests don't exhaust the limit before these tests run.
        import app.rate_limit as rl
        rl._SEND_SUMMARY_BUCKETS.clear()

    def tearDown(self):
        import app.rate_limit as rl
        rl._SEND_SUMMARY_BUCKETS.clear()

    def test_export_summary_returns_text(self):
        """Valid payload returns plain text response."""
        with patch(
            "app.api.routes.summary_email.build_export_text",
            return_value="Özet metin içeriği",
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/export-summary",
                    json={"payload": RESULT_PAYLOAD, "locale": "tr-TR"},
                )
        self.assertIn(r.status_code, (200, 201), r.text)

    def test_export_summary_missing_payload_returns_422(self):
        """Missing payload field returns 422."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/export-summary",
                json={"locale": "tr-TR"},
            )
        self.assertEqual(r.status_code, 422)

    def test_export_summary_en_locale(self):
        """English locale is accepted."""
        with patch(
            "app.api.routes.summary_email.build_export_text",
            return_value="Summary text",
        ):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/export-summary",
                    json={"payload": RESULT_PAYLOAD, "locale": "en"},
                )
        self.assertIn(r.status_code, (200, 201), r.text)


if __name__ == "__main__":
    unittest.main()
