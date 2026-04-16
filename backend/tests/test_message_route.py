"""Tests for POST /v1/session/{session_id}/message (legacy route)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.routes import message as message_routes
from app.api.routes.legacy_deprecation import DEPRECATION_HEADER_VALUE
from app.main import app
from app.models.database import get_db, SessionModel


class _FakeDbSession:
    """Minimal async DB session stub."""

    def __init__(self, session_model=None):
        self._session_model = session_model

    async def get(self, _model_cls, _pk):
        return self._session_model

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


def _override_db_no_session():
    async def _gen():
        yield _FakeDbSession(session_model=None)
    return _gen


def _override_db_with_session(status: str = "chatting"):
    def _make_model():
        m = MagicMock(spec=SessionModel)
        m.status = status
        m.question_count = 0
        return m

    async def _gen():
        yield _FakeDbSession(session_model=_make_model())
    return _gen


class MessageRouteMissingSessionTests(unittest.TestCase):
    """Validation and 404 behaviour when session does not exist in DB."""

    def setUp(self):
        app.dependency_overrides[get_db] = _override_db_no_session()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_missing_body_field_returns_422(self):
        """Pydantic must reject a body that lacks user_input_tr."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/session/any-id/message",
                json={},
            )
        self.assertEqual(r.status_code, 422)

    def test_session_not_found_returns_404(self):
        """When DB has no matching session, the endpoint returns 404."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/session/nonexistent-id/message",
                json={"user_input_tr": "test"},
            )
        self.assertEqual(r.status_code, 404)
        self.assertIn("not found", r.json()["detail"].lower())


class MessageRouteDeprecationHeaderTests(unittest.TestCase):
    """Deprecation header must be present on successful responses.

    Note: FastAPI discards Response object headers when an HTTPException is
    raised, so the header only appears on non-exception paths.
    """

    def test_success_response_carries_deprecation_header(self):
        """On a successful question response the Deprecation header must appear."""
        fake_result = SimpleNamespace(
            action="question",
            message="Kaç gündür şikayetiniz var?",
            question=SimpleNamespace(
                question_tr="Kaç gündür şikayetiniz var?",
                answer_type="free_text",
                choices_tr=[],
            ),
        )

        app.dependency_overrides[get_db] = _override_db_with_session("chatting")
        try:
            with patch.object(
                message_routes.orchestrator,
                "handle_user_answer",
                AsyncMock(return_value=fake_result),
            ), patch.object(
                message_routes.orchestrator,
                "get_session",
                return_value=None,
            ):
                with TestClient(app) as client:
                    r = client.post(
                        "/v1/session/session-abc/message",
                        json={"user_input_tr": "iki gündür"},
                    )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Deprecation"), DEPRECATION_HEADER_VALUE)


class MessageRouteAlreadyCompleteTests(unittest.TestCase):
    """Session with status='done' or 'emergency' must return 400."""

    def _post(self, status: str):
        app.dependency_overrides[get_db] = _override_db_with_session(status)
        try:
            with TestClient(app) as client:
                r = client.post(
                    "/v1/session/done-session/message",
                    json={"user_input_tr": "devam"},
                )
        finally:
            app.dependency_overrides.clear()
        return r

    def test_done_session_returns_400(self):
        r = self._post("done")
        self.assertEqual(r.status_code, 400)
        self.assertIn("already complete", r.json()["detail"].lower())

    def test_emergency_session_returns_400(self):
        r = self._post("emergency")
        self.assertEqual(r.status_code, 400)
        self.assertIn("already complete", r.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
