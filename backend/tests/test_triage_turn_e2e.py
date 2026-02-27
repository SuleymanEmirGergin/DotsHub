"""
E2E-style tests for POST /v1/triage/turn.
Uses TestClient; mocks internal handlers to get deterministic envelope responses.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import triage as triage_routes
from app.models.schemas import Envelope, Meta


def _make_meta():
    return Meta(
        disclaimer_tr="Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır.",
        timestamp=datetime.now(timezone.utc),
    )


class TriageTurnE2ETests(unittest.TestCase):
    """Test POST /v1/triage/turn contract and status codes."""

    def test_turn_returns_envelope_with_type(self):
        """Valid request returns 200 and JSON envelope with type in allowed set."""
        stub = Envelope(
            type="RESULT",
            session_id="test-session-id",
            turn_index=1,
            payload={
                "urgency": "ROUTINE",
                "recommended_specialty": {"id": "neurology", "name_tr": "Nöroloji"},
                "top_conditions": [],
                "doctor_ready_summary_tr": [],
                "safety_notes_tr": [],
            },
            meta=_make_meta(),
        )

        with patch.object(
            triage_routes,
            "_handle_turn_supabase",
            return_value=stub,
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/turn",
                    json={
                        "session_id": None,
                        "locale": "tr-TR",
                        "user_message": "3 gündür başım ağrıyor",
                    },
                )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIn("type", data)
        self.assertIn(data["type"], ("QUESTION", "RESULT", "EMERGENCY", "ERROR"))
        self.assertIn("session_id", data)
        self.assertIn("turn_index", data)
        self.assertIn("payload", data)
        self.assertEqual(data["type"], "RESULT")
        self.assertEqual(data["session_id"], "test-session-id")

    def test_turn_emergency_envelope(self):
        """Mock EMERGENCY response returns 200 with type EMERGENCY."""
        stub = Envelope(
            type="EMERGENCY",
            session_id="emergency-session",
            turn_index=1,
            payload={
                "urgency": "EMERGENCY",
                "reason_tr": "Acil değerlendirme gerekli.",
                "instructions_tr": ["112'yi arayın."],
            },
            meta=_make_meta(),
        )

        with patch.object(
            triage_routes,
            "_handle_turn_supabase",
            return_value=stub,
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/turn",
                    json={
                        "session_id": None,
                        "locale": "tr-TR",
                        "user_message": "göğsüm çok ağrıyor nefes alamıyorum",
                    },
                )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["type"], "EMERGENCY")
        self.assertEqual(data["session_id"], "emergency-session")
        self.assertIn("instructions_tr", data.get("payload", {}))

    def test_turn_empty_input_with_session_returns_error_envelope(self):
        """session_id present but no user_message and no answer -> ERROR envelope."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/turn",
                json={
                    "session_id": "existing-session-id",
                    "locale": "tr-TR",
                    "user_message": "",
                },
            )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["type"], "ERROR")
        self.assertIn("payload", data)
        self.assertIn("message_tr", data["payload"])

    def test_turn_rate_limit_headers_present(self):
        """Response includes X-RateLimit-* headers for /v1/triage/turn."""
        stub = Envelope(
            type="RESULT",
            session_id="rl-session",
            turn_index=1,
            payload={
                "urgency": "ROUTINE",
                "recommended_specialty": {"id": "general", "name_tr": "Genel"},
                "top_conditions": [],
                "doctor_ready_summary_tr": [],
                "safety_notes_tr": [],
            },
            meta=_make_meta(),
        )
        with patch.object(
            triage_routes,
            "_handle_turn_supabase",
            return_value=stub,
        ), patch.object(triage_routes, "_has_supabase", return_value=True):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/turn",
                    json={
                        "session_id": None,
                        "locale": "tr-TR",
                        "user_message": "hafif öksürük",
                    },
                    headers={"x-device-id": "e2e-test-device"},
                )
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)
        self.assertIn("X-RateLimit-Reset", r.headers)


if __name__ == "__main__":
    unittest.main()
