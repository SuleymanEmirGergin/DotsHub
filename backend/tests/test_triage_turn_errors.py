"""Tests for POST /v1/triage/turn error-handling paths.

Covers:
  - RuntimeError → ERROR envelope at 200 OK
  - HTTPException sub-types (503, 404) → re-raised, proper HTTP status
  - ERROR envelope preserves session_id from request
  - PGRST205 / schema-missing exceptions trigger legacy fallback
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import triage as triage_routes
from app.models.schemas import Envelope, Meta

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

BASE_BODY = {"session_id": None, "locale": "tr-TR", "user_message": "başım ağrıyor"}
SESSION_BODY = {
    "session_id": "test-session-123",
    "locale": "tr-TR",
    "user_message": "ağrı",
}


def _stub_envelope(session_id: str = "fallback-session") -> Envelope:
    return Envelope(
        type="QUESTION",
        session_id=session_id,
        turn_index=1,
        payload={"question_tr": "Ağrı ne zaman başladı?"},
        meta=Meta(
            disclaimer_tr="Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır.",
            timestamp=datetime.now(timezone.utc),
        ),
    )


# ─────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────


class TriageTurnErrorHandlingTests(unittest.TestCase):
    """Error-handling paths for POST /v1/triage/turn."""

    # ------------------------------------------------------------------
    # 1. RuntimeError → ERROR envelope (200 OK)
    # ------------------------------------------------------------------
    def test_runtime_error_returns_error_envelope(self):
        """A RuntimeError from _handle_turn_supabase is caught and returned as an
        ERROR envelope with status 200 (not an HTTP error)."""
        with patch.object(
            triage_routes, "_has_supabase", return_value=True
        ), patch.object(
            triage_routes,
            "_handle_turn_supabase",
            side_effect=RuntimeError("db exploded"),
        ):
            with TestClient(app) as client:
                r = client.post("/v1/triage/turn", json=BASE_BODY)

        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["type"], "ERROR")
        self.assertIn("payload", data)
        self.assertIn("code", data["payload"])

    # ------------------------------------------------------------------
    # 2. HTTPException(503) → propagates to 503
    # ------------------------------------------------------------------
    def test_http_503_from_handle_turn_is_reraised(self):
        """An HTTPException(503) from _handle_turn_supabase must propagate as HTTP
        503, not be swallowed into an ERROR envelope."""
        with patch.object(
            triage_routes, "_has_supabase", return_value=True
        ), patch.object(
            triage_routes,
            "_handle_turn_supabase",
            side_effect=HTTPException(status_code=503, detail="Supabase down"),
        ):
            with TestClient(app) as client:
                r = client.post("/v1/triage/turn", json=BASE_BODY)

        self.assertEqual(r.status_code, 503, r.text)

    # ------------------------------------------------------------------
    # 3. HTTPException(404) → propagates to 404
    # ------------------------------------------------------------------
    def test_http_404_from_handle_turn_is_reraised(self):
        """An HTTPException(404) from _handle_turn_supabase must propagate as HTTP
        404 (e.g. session_id not found scenario)."""
        with patch.object(
            triage_routes, "_has_supabase", return_value=True
        ), patch.object(
            triage_routes,
            "_handle_turn_supabase",
            side_effect=HTTPException(status_code=404, detail="session_id not found"),
        ):
            with TestClient(app) as client:
                r = client.post("/v1/triage/turn", json=BASE_BODY)

        self.assertEqual(r.status_code, 404, r.text)

    # ------------------------------------------------------------------
    # 4. ERROR envelope preserves session_id from the request
    # ------------------------------------------------------------------
    def test_error_envelope_preserves_session_id(self):
        """When a RuntimeError occurs for a request with an explicit session_id,
        the returned ERROR envelope echoes back that session_id."""
        with patch.object(
            triage_routes, "_has_supabase", return_value=True
        ), patch.object(
            triage_routes,
            "_handle_turn_supabase",
            side_effect=RuntimeError("timeout"),
        ):
            with TestClient(app) as client:
                r = client.post("/v1/triage/turn", json=SESSION_BODY)

        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["session_id"], "test-session-123")

    # ------------------------------------------------------------------
    # 5. PGRST205 / schema-missing error falls back to legacy handler
    # ------------------------------------------------------------------
    def test_pgrst205_schema_error_falls_back_to_legacy(self):
        """A PGRST205 schema error from _handle_turn_supabase must trigger a
        transparent fallback to _handle_turn_legacy instead of propagating."""
        stub = _stub_envelope("legacy-session")

        with patch.object(
            triage_routes, "_has_supabase", return_value=True
        ), patch.object(
            triage_routes,
            "_handle_turn_supabase",
            side_effect=Exception("PGRST205: relation does not exist"),
        ), patch.object(
            triage_routes,
            "_handle_turn_legacy",
            new=AsyncMock(return_value=stub),
        ) as mock_legacy:
            with TestClient(app) as client:
                r = client.post("/v1/triage/turn", json=BASE_BODY)

        mock_legacy.assert_called_once()
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIn(data["type"], ("QUESTION", "RESULT", "EMERGENCY", "ERROR"))


if __name__ == "__main__":
    unittest.main()
