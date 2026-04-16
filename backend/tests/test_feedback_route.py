"""Tests for POST /v1/triage/feedback endpoint."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

SESSION_UUID = "00000000-0000-0000-0000-000000000001"


class _FakeExecute:
    def __init__(self, data=None):
        self.data = data if data is not None else []


class _FakeQuery:
    """Chainable Supabase query fake."""

    def __init__(self, rows=None):
        self._rows = rows if rows is not None else []

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def insert(self, *_a, **_kw):
        return self

    def execute(self):
        return _FakeExecute(self._rows)


class FeedbackRouteTests(unittest.TestCase):
    """Contract tests for POST /v1/triage/feedback."""

    def _make_sb(self, session_exists: bool = True, insert_ok: bool = True):
        """Return a fake Supabase client."""
        sb = MagicMock()
        session_data = [{"id": SESSION_UUID}] if session_exists else []

        def table_factory(name: str):
            if name == "triage_sessions":
                return _FakeQuery(session_data)
            if name == "triage_feedback":
                insert_q = MagicMock()
                insert_q.execute.return_value = _FakeExecute([{"id": 1}] if insert_ok else None)
                return MagicMock(insert=lambda *a, **kw: insert_q)
            return _FakeQuery()

        sb.table.side_effect = table_factory
        return sb

    def test_valid_up_feedback_returns_ok(self):
        """Valid 'up' rating returns 201 with ok=True (200 until SEM-1 lands)."""
        with patch("app.api.routes.feedback.get_supabase", return_value=self._make_sb()):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/feedback",
                    json={
                        "session_id": SESSION_UUID,
                        "rating": "up",
                        "comment": None,
                        "user_selected_specialty_id": None,
                    },
                )
        # SEM-1: will be 201 after route is updated; accept 200 in the interim
        self.assertIn(r.status_code, (200, 201), r.text)
        self.assertTrue(r.json().get("ok"))

    def test_valid_down_feedback_with_comment(self):
        """'down' rating with comment returns 201 (200 until SEM-1 lands)."""
        with patch("app.api.routes.feedback.get_supabase", return_value=self._make_sb()):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/feedback",
                    json={
                        "session_id": SESSION_UUID,
                        "rating": "down",
                        "comment": "Yanlış branş önerisi",
                        "user_selected_specialty_id": None,
                    },
                )
        # SEM-1: will be 201 after route is updated; accept 200 in the interim
        self.assertIn(r.status_code, (200, 201), r.text)

    def test_invalid_rating_returns_422(self):
        """Rating field only accepts 'up' or 'down'."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/feedback",
                json={
                    "session_id": SESSION_UUID,
                    "rating": "maybe",
                },
            )
        self.assertEqual(r.status_code, 422)

    def test_missing_session_id_returns_422(self):
        """Request without session_id fails validation."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/feedback",
                json={"rating": "up"},
            )
        self.assertEqual(r.status_code, 422)

    def test_session_not_found_returns_404(self):
        """404 when session_id does not exist in database."""
        with patch("app.api.routes.feedback.get_supabase", return_value=self._make_sb(session_exists=False)):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/feedback",
                    json={
                        "session_id": SESSION_UUID,
                        "rating": "up",
                    },
                )
        self.assertEqual(r.status_code, 404)

    def test_comment_too_long_returns_422(self):
        """Comment exceeding 2000 chars fails validation."""
        with TestClient(app) as client:
            r = client.post(
                "/v1/triage/feedback",
                json={
                    "session_id": SESSION_UUID,
                    "rating": "up",
                    "comment": "x" * 2001,
                },
            )
        self.assertEqual(r.status_code, 422)

    # ── GAP-2: DB failure tests ────────────────────────────────────────────────

    def test_insert_failure_data_none_returns_500(self):
        """When insert returns data=None the route raises 500."""
        # Build a fake whose .data is genuinely None (not the empty-list fallback
        # in _FakeExecute) to trigger the `if ins.data is None` branch in the route.
        class _NoneDataExecute:
            data = None

        sb = MagicMock()
        session_q = MagicMock()
        session_q.execute.return_value = MagicMock(data=[{"id": SESSION_UUID}])
        insert_q = MagicMock()
        insert_q.execute.return_value = _NoneDataExecute()

        def table_factory(name):
            if name == "triage_sessions":
                tq = MagicMock()
                tq.select.return_value.eq.return_value.limit.return_value = session_q
                return tq
            if name == "triage_feedback":
                tq = MagicMock()
                tq.insert.return_value = insert_q
                return tq
            return MagicMock()

        sb.table.side_effect = table_factory
        with patch("app.api.routes.feedback.get_supabase", return_value=sb):
            with TestClient(app) as client:
                r = client.post(
                    "/v1/triage/feedback",
                    json={"session_id": SESSION_UUID, "rating": "up"},
                )
        self.assertEqual(r.status_code, 500)

    def test_insert_supabase_raises_returns_5xx(self):
        """When insert.execute() raises RuntimeError the route returns 5xx.

        The route does not currently catch RuntimeError, so it propagates as an
        unhandled 500.  raise_server_exceptions=False lets us inspect the status
        code instead of having the TestClient re-raise the exception.
        """
        sb = MagicMock()

        session_q = MagicMock()
        session_q.execute.return_value = MagicMock(data=[{"id": SESSION_UUID}])

        insert_q = MagicMock()
        insert_q.execute.side_effect = RuntimeError("connection refused")

        def table_factory(name):
            if name == "triage_sessions":
                tq = MagicMock()
                tq.select.return_value.eq.return_value.limit.return_value = session_q
                return tq
            if name == "triage_feedback":
                tq = MagicMock()
                tq.insert.return_value = insert_q
                return tq
            return MagicMock()

        sb.table.side_effect = table_factory
        with patch("app.api.routes.feedback.get_supabase", return_value=sb):
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    "/v1/triage/feedback",
                    json={"session_id": SESSION_UUID, "rating": "down"},
                )
        self.assertIn(r.status_code, (500, 503))

    def test_session_lookup_raises_returns_5xx(self):
        """When session lookup raises RuntimeError the route returns 5xx.

        Uses raise_server_exceptions=False so the TestClient returns the 500
        response rather than re-raising the unhandled exception.
        """
        sb = MagicMock()
        lookup_q = MagicMock()
        lookup_q.execute.side_effect = RuntimeError("timeout")
        tq = MagicMock()
        tq.select.return_value.eq.return_value.limit.return_value = lookup_q
        sb.table.return_value = tq
        with patch("app.api.routes.feedback.get_supabase", return_value=sb):
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    "/v1/triage/feedback",
                    json={"session_id": SESSION_UUID, "rating": "up"},
                )
        self.assertIn(r.status_code, (500, 503))


if __name__ == "__main__":
    unittest.main()
