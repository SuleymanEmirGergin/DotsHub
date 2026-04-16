"""Edge-case tests for admin_v5 endpoints.

Covers:
- EmptyDatasetOverviewTests  – overview_stats with 0 rows
- SessionListFilterTests      – list_sessions filter parameters
- SessionDetailNotFoundTests  – 404 / 503 paths in get_session_detail
- FeedbackStatsEdgeCaseTests  – feedback_stats with 0 rows and boundary days
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import admin_v5
from app.main import app


# ---------------------------------------------------------------------------
# Shared fake Supabase infrastructure (copied from test_admin_v5_stats.py)
# ---------------------------------------------------------------------------


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
    """Fake Supabase with both RESULT and EMERGENCY sessions."""

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


# ---------------------------------------------------------------------------
# Helper: supabase that returns nothing for every table
# ---------------------------------------------------------------------------


class _EmptySB:
    """Supabase stub that returns 0 rows for every table."""

    def table(self, name: str):
        return _FakeQuery(name, [])


# ---------------------------------------------------------------------------
# Helper: supabase that raises on every .execute() call
# ---------------------------------------------------------------------------


class _RaisingQuery:
    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def gte(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def single(self):
        return self

    def execute(self):
        raise RuntimeError("Supabase down")


class _RaisingSB:
    def table(self, name: str):
        return _RaisingQuery()


# ---------------------------------------------------------------------------
# Class 1: EmptyDatasetOverviewTests
# ---------------------------------------------------------------------------


class EmptyDatasetOverviewTests(unittest.TestCase):
    """overview_stats behaviour when the database contains 0 sessions."""

    def _get_overview(self, sb):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", sb),
        ):
            with TestClient(app) as client:
                return client.get(
                    "/admin/stats/overview",
                    headers={"x-admin-key": "secret"},
                )

    def test_overview_empty_db_health_is_info(self):
        """With 0 sessions (< min_samples), health.overall must be 'INFO'."""
        r = self._get_overview(_EmptySB())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["health"]["overall"], "INFO")

    def test_overview_empty_db_zero_rates(self):
        """With 0 sessions, low_conf_rate and high_risk_rate must be 0.0."""
        r = self._get_overview(_EmptySB())
        self.assertEqual(r.status_code, 200)
        health = r.json()["health"]
        self.assertEqual(health["low_conf_rate"], 0.0)
        self.assertEqual(health["high_risk_rate"], 0.0)

    def test_overview_empty_top_lists_are_empty(self):
        """With 0 sessions, top_stop_reasons and top_canonicals must be []."""
        r = self._get_overview(_EmptySB())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["top_stop_reasons"], [])
        self.assertEqual(body["top_canonicals"], [])


# ---------------------------------------------------------------------------
# Class 2: SessionListFilterTests
# ---------------------------------------------------------------------------


class SessionListFilterTests(unittest.TestCase):
    """list_sessions filter parameter behaviour."""

    def _get_sessions(self, sb, params: str = ""):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", sb),
        ):
            with TestClient(app) as client:
                return client.get(
                    f"/admin/sessions{params}",
                    headers={"x-admin-key": "secret"},
                )

    def test_sessions_filter_by_envelope_type(self):
        """?envelope_type=RESULT — all returned items have envelope_type == 'RESULT'."""
        r = self._get_sessions(_FakeSupabase(), "?envelope_type=RESULT")
        self.assertEqual(r.status_code, 200)
        items = r.json()["items"]
        self.assertTrue(len(items) > 0, "Expected at least one RESULT session")
        for item in items:
            self.assertEqual(item["envelope_type"], "RESULT")

    def test_sessions_only_problems_filter(self):
        """?only_problems=1 returns 200 and items is a list."""
        r = self._get_sessions(_FakeSupabase(), "?only_problems=1")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json()["items"], list)

    def test_sessions_empty_result_returns_empty_list(self):
        """When supabase returns 0 rows, items == []."""
        r = self._get_sessions(_EmptySB())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["items"], [])


# ---------------------------------------------------------------------------
# Class 3: SessionDetailNotFoundTests
# ---------------------------------------------------------------------------


class SessionDetailNotFoundTests(unittest.TestCase):
    """get_session_detail 404 / 503 edge cases (BUG-A fixes)."""

    def _get_detail(self, sb, session_id: str):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", sb),
        ):
            with TestClient(app) as client:
                return client.get(
                    f"/admin/sessions/{session_id}",
                    headers={"x-admin-key": "secret"},
                )

    def test_nonexistent_session_id_returns_404(self):
        """Empty supabase → .single() returns None data → HTTP 404."""
        r = self._get_detail(_EmptySB(), "nonexistent-id")
        self.assertEqual(r.status_code, 404)

    def test_supabase_exception_returns_503(self):
        """_RaisingSB.execute() raises RuntimeError → _sb_execute wraps it as HTTP 503."""
        r = self._get_detail(_RaisingSB(), "any-id")
        self.assertEqual(r.status_code, 503)


# ---------------------------------------------------------------------------
# Class 4: FeedbackStatsEdgeCaseTests
# ---------------------------------------------------------------------------


class FeedbackStatsEdgeCaseTests(unittest.TestCase):
    """feedback_stats edge cases: 0 rows and boundary day values."""

    def _get_feedback_stats(self, sb, params: str = ""):
        with (
            patch("app.admin_auth.settings.ADMIN_API_KEY", "secret"),
            patch.object(admin_v5, "supabase", sb),
        ):
            with TestClient(app) as client:
                return client.get(
                    f"/admin/feedback/stats{params}",
                    headers={"x-admin-key": "secret"},
                )

    def test_feedback_stats_zero_rows_returns_valid_response(self):
        """0 feedback rows → total==0, satisfaction_pct==0.0, trend==[]."""
        r = self._get_feedback_stats(_EmptySB())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["satisfaction_pct"], 0.0)
        self.assertEqual(body["trend"], [])

    def test_feedback_stats_days_boundary_values(self):
        """days=1 and days=90 both return 200."""
        for days in (1, 90):
            with self.subTest(days=days):
                r = self._get_feedback_stats(_EmptySB(), f"?days={days}")
                self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
