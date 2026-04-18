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

    def execute(self):
        data = list(self.rows)
        for col, val in self.eq_filters:
            data = [row for row in data if row.get(col) == val]
        for col, vals in self.in_filters:
            data = [row for row in data if row.get(col) in vals]
        if self._limit is not None:
            data = data[: self._limit]
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
                "envelope_type": "EMERGENCY",
                "stop_reason": "emergency_detected",
                "confidence_0_1": 0.9,
                "recommended_specialty_tr": "Acil",
                "recommended_specialty_id": "emergency",
                "extracted_canonicals": ["chest_pain"],
                "meta": {"risk_level": "HIGH", "risk_score_0_1": 0.95},
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
            {
                "id": "fb-2",
                "session_id": "session-2",
                "rating": "up",
                "comment": None,
                "user_selected_specialty_id": None,
                "created_at": "2026-02-12T09:10:00Z",
            },
        ]

    def table(self, table_name: str):
        if table_name == "triage_sessions":
            return _FakeQuery(table_name, self._sessions)
        if table_name == "triage_feedback":
            return _FakeQuery(table_name, self._feedback)
        return _FakeQuery(table_name, [])


class AdminV5AuthTests(unittest.TestCase):
    # admin_v5_router is mounted at /v1 (main.py) so the admin_v5
    # endpoints (which carry their own prefix="/admin") land at
    # /v1/admin/*. The /v1 prefix was added so the admin rate-limit
    # middleware (which gates /v1/admin/*) actually covers these
    # routes — before, they were at /admin/* and bypassed the limit.
    def _get_sessions(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/sessions?limit=1", headers=headers or {})

    def _get_feedback_stats(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/feedback/stats?days=30", headers=headers or {})

    def _get_feedback_list(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/admin/feedback/list?limit=20", headers=headers or {})

    def test_returns_503_when_admin_key_missing(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", ""):
            response = self._get_sessions(headers={"x-admin-key": "anything"})

        self.assertEqual(response.status_code, 503)

    def test_returns_401_when_header_missing(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._get_sessions()

        self.assertEqual(response.status_code, 401)

    def test_returns_401_when_header_invalid(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._get_sessions(headers={"x-admin-key": "wrong"})

        self.assertEqual(response.status_code, 401)

    def test_allows_request_with_valid_header(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            response = self._get_sessions(headers={"x-admin-key": "secret"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())

    def test_feedback_stats_requires_admin_header(self):
        with patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"):
            response = self._get_feedback_stats()

        self.assertEqual(response.status_code, 401)

    def test_feedback_endpoints_with_valid_header(self):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", _FakeSupabase()),
        ):
            stats_resp = self._get_feedback_stats(headers={"x-admin-key": "secret"})
            list_resp = self._get_feedback_list(headers={"x-admin-key": "secret"})

        self.assertEqual(stats_resp.status_code, 200)
        stats = stats_resp.json()
        self.assertEqual(stats.get("total"), 2)
        self.assertIn("trend", stats)
        self.assertIn("top_down_specialties", stats)

        self.assertEqual(list_resp.status_code, 200)
        data = list_resp.json()
        self.assertEqual(data.get("count"), 2)
        self.assertTrue(data.get("items"))
        self.assertEqual(data["items"][0].get("session_specialty"), "Noroloji")


if __name__ == "__main__":
    unittest.main()
