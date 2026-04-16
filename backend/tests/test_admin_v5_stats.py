from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import admin_v5
from app.main import app


class _FakeExecute:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table_name: str, rows: list[dict]):
        self.table_name = table_name
        self.rows = rows
        self.eq_filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, set[object]]] = []
        self._limit: int | None = None
        self._single = False

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        if _args:
            col = str(_args[0])
            val = _args[1] if len(_args) > 1 else None
            self.eq_filters.append((col, val))
        return self

    def in_(self, *_args, **_kwargs):
        if _args:
            col = str(_args[0])
            vals = set(_args[1]) if len(_args) > 1 else set()
            self.in_filters.append((col, vals))
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        if _args:
            self._limit = int(_args[0])
        return self

    def single(self):
        self._single = True
        return self

    def delete(self):
        return self

    def execute(self):
        data = list(self.rows)
        for col, val in self.eq_filters:
            data = [row for row in data if row.get(col) == val]
        for col, vals in self.in_filters:
            data = [row for row in data if row.get(col) in vals]
        if self._limit is not None:
            data = data[: self._limit]
        if self._single:
            return _FakeExecute(data[0] if data else None)
        return _FakeExecute(data)


class _FakeSupabase:
    def __init__(self):
        self._sessions = [
            {
                "id": "session-1",
                "session_id": "session-1",
                "created_at": "2026-02-10T10:00:00Z",
                "updated_at": "2026-02-10T10:05:00Z",
                "envelope_type": "RESULT",
                "stop_reason": "min_expected_gain",
                "confidence_0_1": 0.42,
                "recommended_specialty_tr": "Noroloji",
                "recommended_specialty_id": "neurology",
                "extracted_canonicals": ["headache"],
                "meta": {"risk": {"level": "LOW", "score_0_1": 0.2}},
            },
            {
                "id": "session-2",
                "session_id": "session-2",
                "created_at": "2026-02-11T12:00:00Z",
                "updated_at": "2026-02-11T12:02:00Z",
                "envelope_type": "RESULT",
                "stop_reason": "emergency_detected",
                "confidence_0_1": 0.9,
                "recommended_specialty_tr": "Acil",
                "recommended_specialty_id": "emergency",
                "extracted_canonicals": ["chest_pain"],
                "meta": {"risk": {"level": "HIGH", "score_0_1": 0.95}},
            },
        ]
        self._events = [
            {
                "id": "evt-1",
                "session_id": "session-1",
                "event_type": "question_asked",
                "created_at": "2026-02-10T10:01:00Z",
            },
            {
                "id": "evt-2",
                "session_id": "session-1",
                "event_type": "answer_given",
                "created_at": "2026-02-10T10:02:00Z",
            },
        ]
        self._feedback = [
            {
                "id": "fb-1",
                "session_id": "session-1",
                "rating": "down",
                "comment": "Yanlış branş önerisi",
                "user_selected_specialty_id": None,
                "created_at": "2026-02-12T09:00:00Z",
            },
        ]

    def table(self, table_name: str):
        if table_name == "triage_sessions":
            return _FakeQuery(table_name, self._sessions)
        if table_name == "triage_events":
            return _FakeQuery(table_name, self._events)
        if table_name == "triage_feedback":
            return _FakeQuery(table_name, self._feedback)
        return _FakeQuery(table_name, [])


class SessionDetailTests(unittest.TestCase):
    """Tests for GET /admin/sessions/{session_id}."""

    def _get_session(self, session_id: str, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get(f"/admin/sessions/{session_id}", headers=headers or {})

    def test_session_detail_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._get_session("session-1")
        self.assertEqual(r.status_code, 401)

    def test_session_detail_with_valid_key(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._get_session("session-1", headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("session", body)
        self.assertIn("events", body)
        self.assertIn("feedback", body)

    def test_session_detail_events_belong_to_session(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._get_session("session-1", headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsNotNone(body["session"])
        # Both events belong to session-1
        self.assertEqual(len(body["events"]), 2)
        # One feedback entry belongs to session-1
        self.assertEqual(len(body["feedback"]), 1)


class OverviewStatsTests(unittest.TestCase):
    """Tests for GET /admin/stats/overview."""

    def _get_overview(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/admin/stats/overview", headers=headers or {})

    def test_overview_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._get_overview()
        self.assertEqual(r.status_code, 401)

    def test_overview_with_valid_key(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._get_overview(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("total", body)
        self.assertIn("health", body)
        self.assertIn("by_envelope_type", body)

    def test_overview_health_shape(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._get_overview(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        health = r.json()["health"]
        self.assertIn("overall", health)
        self.assertIn("samples", health)
        self.assertIn("low_conf_rate", health)
        self.assertIn("high_risk_rate", health)


class LowConfSeriesTests(unittest.TestCase):
    """Tests for GET /admin/stats/low_conf_series."""

    def _get_low_conf(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/admin/stats/low_conf_series", headers=headers or {})

    def test_low_conf_series_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._get_low_conf()
        self.assertEqual(r.status_code, 401)

    def test_low_conf_series_returns_points(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._get_low_conf(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("points", body)
        self.assertIsInstance(body["points"], list)


class RiskHighSeriesTests(unittest.TestCase):
    """Tests for GET /admin/stats/risk_high_series."""

    def _get_risk_high(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/admin/stats/risk_high_series", headers=headers or {})

    def test_risk_high_series_requires_admin(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            r = self._get_risk_high()
        self.assertEqual(r.status_code, 401)

    def test_risk_high_series_returns_points(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            r = self._get_risk_high(headers={"x-admin-key": "secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("points", body)
        self.assertIsInstance(body["points"], list)


if __name__ == "__main__":
    unittest.main()
