"""Tests for legacy session routes (/v1/session/...)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.routes import session as session_routes
from app.api.routes.legacy_deprecation import DEPRECATION_HEADER_VALUE
from app.main import app
from app.models.database import get_db


class _FakeDbSession:
    def add(self, _obj) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def execute(self, _stmt):
        mock = MagicMock()
        mock.scalars.return_value.all.return_value = []
        return mock


async def _override_get_db():
    yield _FakeDbSession()


class SessionStartValidationTests(unittest.TestCase):
    """POST /v1/session/start — validation and deprecation headers."""

    def test_missing_body_returns_422(self):
        """Pydantic must reject a body that lacks user_input_tr."""
        with TestClient(app) as client:
            r = client.post("/v1/session/start", json={})
        self.assertEqual(r.status_code, 422)

    def test_start_returns_deprecation_header(self):
        """Successful start response must carry the Deprecation header."""
        fake_result = SimpleNamespace(
            action="emergency",
            message="Acil durum.",
            emergency=SimpleNamespace(
                reason="Acil değerlendirme gerekli.",
                emergency_instructions=["112'yi arayın."],
                missing_info_to_confirm=[],
            ),
        )

        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(
                session_routes.orchestrator,
                "handle_initial_symptoms",
                AsyncMock(return_value=fake_result),
            ):
                with TestClient(app) as client:
                    r = client.post(
                        "/v1/session/start",
                        json={"user_input_tr": "nefes alamıyorum"},
                    )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Deprecation"), DEPRECATION_HEADER_VALUE)


class SessionResultEndpointTests(unittest.TestCase):
    """GET /v1/session/{session_id}/result — orchestrator-based checks."""

    def _get_result(self, session_id: str = "unknown-session"):
        with TestClient(app) as client:
            return client.get(f"/v1/session/{session_id}/result")

    def test_unknown_session_returns_400(self):
        """Orchestrator has no state for the session → 400."""
        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(session_routes.orchestrator, "get_session", return_value=None):
                r = self._get_result("no-such-session")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(r.status_code, 400)

    def test_incomplete_session_returns_400(self):
        """Orchestrator has state but session is not complete → 400."""
        incomplete = SimpleNamespace(is_complete=False, reasoning_output=None)

        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(session_routes.orchestrator, "get_session", return_value=incomplete):
                r = self._get_result("incomplete-session")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(r.status_code, 400)

    def test_result_detail_message(self):
        """400 detail message must mention 'not yet complete'."""
        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(session_routes.orchestrator, "get_session", return_value=None):
                r = self._get_result("gone")
        finally:
            app.dependency_overrides.clear()
        self.assertIn("not yet complete", r.json()["detail"].lower())


class SessionStateEndpointTests(unittest.TestCase):
    """GET /v1/session/{session_id}/state — no DB dependency."""

    def _get_state(self, session_id: str = "unknown-session"):
        with TestClient(app) as client:
            return client.get(f"/v1/session/{session_id}/state")

    def test_unknown_session_returns_404(self):
        """Orchestrator returns None → 404."""
        with patch.object(session_routes.orchestrator, "get_session", return_value=None):
            r = self._get_state("ghost-session")
        self.assertEqual(r.status_code, 404)

    def test_known_session_returns_200(self):
        """Orchestrator returns a state dict → 200."""
        fake_state = SimpleNamespace(to_state_dict=lambda: {"session_id": "ok-session"})
        with patch.object(session_routes.orchestrator, "get_session", return_value=fake_state):
            r = self._get_state("ok-session")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("session_id"), "ok-session")

    def test_state_404_detail(self):
        """404 detail message must say 'not found'."""
        with patch.object(session_routes.orchestrator, "get_session", return_value=None):
            r = self._get_state("any")
        self.assertIn("not found", r.json()["detail"].lower())


class SessionSummaryEndpointTests(unittest.TestCase):
    """GET /v1/session/{session_id}/summary — orchestrator-based checks."""

    def test_unknown_session_returns_400(self):
        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(session_routes.orchestrator, "get_session", return_value=None):
                with TestClient(app) as client:
                    r = client.get("/v1/session/missing/summary")
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(r.status_code, 400)

    def test_summary_400_detail(self):
        """400 detail message must mention 'not yet complete'."""
        app.dependency_overrides[get_db] = _override_get_db
        try:
            with patch.object(session_routes.orchestrator, "get_session", return_value=None):
                with TestClient(app) as client:
                    r = client.get("/v1/session/missing/summary")
        finally:
            app.dependency_overrides.clear()
        self.assertIn("not yet complete", r.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
