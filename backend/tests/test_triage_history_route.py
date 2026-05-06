from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import triage as triage_routes
from app.main import app


class _FakeExecute:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self):
        self.eq_filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, tuple[object, ...]]] = []
        self.limit_value: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value: object):
        self.eq_filters.append((column, value))
        return self

    def in_(self, column: str, values):
        self.in_filters.append((column, tuple(values)))
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def execute(self):
        # Two rows on purpose: one RESULT row (no emergency_reason_tr)
        # and one EMERGENCY row carrying the suspected-condition phrase.
        # Lets a single test exercise both the empty + populated branches
        # for the new field without doubling the test count.
        return _FakeExecute(
            [
                {
                    "id": "session-1",
                    "created_at": "2026-02-12T10:00:00Z",
                    "envelope_type": "RESULT",
                    "recommended_specialty_tr": "Dahiliye",
                    "confidence_label_tr": "orta",
                    "confidence_0_1": 0.62,
                    "stop_reason": "min_expected_gain",
                    "emergency_reason_tr": None,
                },
                {
                    "id": "session-2",
                    "created_at": "2026-02-13T03:44:00Z",
                    "envelope_type": "EMERGENCY",
                    "recommended_specialty_tr": "Acil Tıp",
                    "confidence_label_tr": None,
                    "confidence_0_1": None,
                    "stop_reason": "emergency_rule",
                    "emergency_reason_tr": (
                        "Akut koroner sendrom acil değerlendirme gerektirebilir."
                    ),
                },
            ]
        )


class _FakeSupabase:
    def __init__(self, query: _FakeQuery):
        self.query = query
        self.table_calls: list[str] = []

    def table(self, table_name: str):
        self.table_calls.append(table_name)
        return self.query


class TriageHistoryRouteTests(unittest.TestCase):
    def _get_history(self, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get("/v1/triage/history?limit=150", headers=headers or {})

    def test_returns_empty_when_supabase_disabled(self):
        with patch.object(triage_routes, "_has_supabase", return_value=False):
            response = self._get_history(headers={"x-device-id": "device-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})

    def test_returns_empty_when_device_header_missing(self):
        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase") as mocked_get_supabase,
        ):
            response = self._get_history()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})
        mocked_get_supabase.assert_not_called()

    def test_filters_by_device_id_and_completed_envelopes(self):
        fake_query = _FakeQuery()
        fake_supabase = _FakeSupabase(fake_query)

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake_supabase),
        ):
            response = self._get_history(headers={"x-device-id": "device-42"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_supabase.table_calls, ["triage_sessions"])
        self.assertIn(("device_id", "device-42"), fake_query.eq_filters)
        self.assertIn(
            ("envelope_type", ("RESULT", "EMERGENCY", "SAME_DAY")),
            fake_query.in_filters,
        )
        self.assertEqual(fake_query.limit_value, 100)
        self.assertEqual(response.json()["items"][0]["id"], "session-1")

    def test_emergency_reason_tr_round_trips(self):
        """Mobile #38's emergency History card needs the suspected
        condition phrase from the triage envelope. The history endpoint
        used to drop it during projection — this test pins it back in."""
        fake_query = _FakeQuery()
        fake_supabase = _FakeSupabase(fake_query)

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake_supabase),
        ):
            response = self._get_history(headers={"x-device-id": "device-99"})

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        # RESULT row: emergency_reason_tr surfaces as null.
        result_row = next(r for r in items if r["envelope_type"] == "RESULT")
        self.assertIsNone(result_row.get("emergency_reason_tr"))
        # EMERGENCY row: phrase round-trips verbatim so the mobile card
        # can render "{label} OLABİLİR." without backend re-shaping.
        emergency_row = next(r for r in items if r["envelope_type"] == "EMERGENCY")
        self.assertEqual(
            emergency_row["emergency_reason_tr"],
            "Akut koroner sendrom acil değerlendirme gerektirebilir.",
        )


if __name__ == "__main__":
    unittest.main()
