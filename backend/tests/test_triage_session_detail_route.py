"""Tests for ``GET /v1/triage/sessions/{session_id}``.

Drives the mobile History → Detail drill-down. Coverage focuses on the
two non-obvious requirements:

  1. **Ownership scoping** — a session is only visible to the device
     that created it. Wrong device id must 404 (not 403), so an
     attacker can't enumerate session ids by membership probing.

  2. **Privacy projection** — the response strips the device_id (the
     caller just confirmed it via the header) and excludes the heavy
     debug blobs (specialty_scoring_debug, question_selector_debug,
     confidence_debug, meta) we keep server-side for tuning.

Mocks the Supabase client because the interesting behaviour lives in
the route's projection + ownership check.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import triage as triage_routes
from app.main import app


class _FakeExecute:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, response_rows: list[dict]) -> None:
        self.response_rows = response_rows
        self.eq_filters: list[tuple[str, object]] = []
        self.last_select: str | None = None
        self.limit_value: int | None = None

    def select(self, columns: str, *_args, **_kwargs):
        self.last_select = columns
        return self

    def eq(self, column: str, value: object):
        self.eq_filters.append((column, value))
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def execute(self):
        return _FakeExecute(self.response_rows)


class _FakeSupabase:
    def __init__(self, query: _FakeQuery) -> None:
        self.query = query
        self.table_calls: list[str] = []

    def table(self, name: str):
        self.table_calls.append(name)
        return self.query


_SESSION_ID = "00000000-0000-4000-a000-000000000001"
_DEVICE_OWNER = "device-owner"
_DEVICE_OTHER = "device-stranger"


# Realistic stored row, including all the columns the detail screen
# actually renders. `device_id` is intentionally present here — the
# route should strip it before returning.
def _stored_row() -> dict:
    return {
        "id": _SESSION_ID,
        "session_id": _SESSION_ID,
        "device_id": _DEVICE_OWNER,
        "created_at": "2026-04-28T14:32:00Z",
        "updated_at": "2026-04-28T14:34:00Z",
        "envelope_type": "RESULT",
        "turn_index": 5,
        "stop_reason": "min_expected_gain",
        "locale": "tr-TR",
        "recommended_specialty_id": "neurology",
        "recommended_specialty_tr": "Nöroloji",
        "confidence_0_1": 0.83,
        "confidence_label_tr": "yüksek",
        "confidence_explain_tr": "Belirti örüntüsü migren ile uyumlu.",
        "top_conditions": [
            {"disease_label": "Migraine", "score_0_1": 0.83},
            {"disease_label": "Sinusitis", "score_0_1": 0.11},
        ],
        "why_specialty_tr": [
            "Tek taraflı zonklayıcı baş ağrısı",
            "Işığa hassasiyet",
        ],
        "emergency_rule_id": None,
        "emergency_reason_tr": None,
        "input_text": "Üç gündür şiddetli baş ağrım var",
        "asked_canonicals": ["bulantı", "fotofobi"],
        "extracted_canonicals": ["baş_ağrısı", "fotofobi"],
        "user_canonicals_tr": ["baş ağrısı", "ışığa hassasiyet"],
    }


class TestTriageSessionDetailRoute(unittest.TestCase):
    def _get(self, session_id: str, headers: dict[str, str] | None = None):
        with TestClient(app) as client:
            return client.get(
                f"/v1/triage/sessions/{session_id}",
                headers=headers or {},
            )

    def test_missing_device_id_returns_400(self) -> None:
        # Without a device id we can't enforce ownership; 400 keeps us
        # from accidentally serving a row when the header is just
        # truncated by a misconfigured proxy.
        response = self._get(_SESSION_ID)
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "missing_device_id")

    def test_returns_row_with_device_id_stripped(self) -> None:
        fake_query = _FakeQuery(response_rows=[_stored_row()])
        fake_sb = _FakeSupabase(fake_query)

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake_sb),
        ):
            response = self._get(
                _SESSION_ID, headers={"X-Device-Id": _DEVICE_OWNER}
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], _SESSION_ID)
        self.assertEqual(body["recommended_specialty_tr"], "Nöroloji")
        self.assertEqual(body["top_conditions"][0]["disease_label"], "Migraine")
        # Privacy: the device_id confirmed via header should NOT round-
        # trip through the response. Keeps it off any log that captures
        # response bodies.
        self.assertNotIn("device_id", body)
        # Heavy debug blobs must not leak (they're for tuning, not the
        # user-facing detail screen).
        self.assertNotIn("specialty_scoring_debug", body)
        self.assertNotIn("question_selector_debug", body)
        self.assertNotIn("confidence_debug", body)

    def test_filters_select_uses_explicit_column_set(self) -> None:
        # The exact projection list matters: it's how we ensure debug
        # columns can never reach the client. If someone replaces the
        # SELECT with `*` this assertion catches them.
        fake_query = _FakeQuery(response_rows=[_stored_row()])
        fake_sb = _FakeSupabase(fake_query)

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake_sb),
        ):
            self._get(_SESSION_ID, headers={"X-Device-Id": _DEVICE_OWNER})

        select_columns = fake_query.last_select or ""
        self.assertIn("recommended_specialty_tr", select_columns)
        self.assertIn("top_conditions", select_columns)
        self.assertIn("emergency_reason_tr", select_columns)
        self.assertNotIn("specialty_scoring_debug", select_columns)
        self.assertNotIn("question_selector_debug", select_columns)
        self.assertNotIn("meta", select_columns)

    def test_other_device_gets_404(self) -> None:
        # Supabase eq("device_id", other) returns no rows. Route must
        # 404 — NOT 403 — so an attacker can't enumerate session ids
        # by probing for membership.
        fake_query = _FakeQuery(response_rows=[])
        fake_sb = _FakeSupabase(fake_query)

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake_sb),
        ):
            response = self._get(
                _SESSION_ID, headers={"X-Device-Id": _DEVICE_OTHER}
            )

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["detail"]["code"], "not_found")
        # Verify the query DID enforce the device_id filter.
        self.assertIn(("device_id", _DEVICE_OTHER), fake_query.eq_filters)

    def test_supabase_unavailable_returns_404(self) -> None:
        # Dev environments without Supabase should look indistinguishable
        # from "session not found" so production-mode behaviour stays
        # consistent.
        with patch.object(triage_routes, "_has_supabase", return_value=False):
            response = self._get(
                _SESSION_ID, headers={"X-Device-Id": _DEVICE_OWNER}
            )

        self.assertEqual(response.status_code, 404)

    def test_supabase_exception_returns_503(self) -> None:
        # Storage outage with the env wired up: distinct from 404 so
        # Sentry / ops can alert on transient failures without mixing
        # them with "user typed a wrong id."
        fake_sb = type(
            "_BoomSb",
            (),
            {
                "table": lambda self, _name: (_ for _ in ()).throw(
                    RuntimeError("supabase down"),
                ),
            },
        )()

        with (
            patch.object(triage_routes, "_has_supabase", return_value=True),
            patch("app.supabase_client.get_supabase", return_value=fake_sb),
        ):
            response = self._get(
                _SESSION_ID, headers={"X-Device-Id": _DEVICE_OWNER}
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"], "session_detail_unavailable"
        )


if __name__ == "__main__":
    unittest.main()
