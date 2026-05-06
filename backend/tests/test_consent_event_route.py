"""Tests for ``POST /v1/consent/event`` — per-clause consent audit log.

Mocks the Supabase client wholesale because:
  - The interesting behaviour lives in the route's validation +
    error translation, not in the storage layer.
  - The KVKK auditor's read path is direct-against-Supabase with a
    different role; testing it via this module would be testing the
    Supabase client itself.

Coverage:
  - Happy path: insert returns an id, response surfaces it.
  - Each of the three valid `clause_id` values reaches the table.
  - Un-tick (accepted=false) is recorded same as tick.
  - Missing X-Device-Id → 400 with `missing_device_id`.
  - Bad clause_id → 422 (Pydantic).
  - Supabase exception → 503 with `audit_log_unavailable`.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


class _FakeInsertResp:
    """Mimic supabase-py's response.data shape for an insert that
    returns the generated row(s)."""

    def __init__(self, rows: list[dict]) -> None:
        self.data = rows


class _FakeTable:
    def __init__(self, response_rows: list[dict]) -> None:
        self.response_rows = response_rows
        self.last_payload: dict | None = None

    def insert(self, payload: dict) -> "_FakeTable":
        self.last_payload = payload
        return self

    def execute(self) -> _FakeInsertResp:
        return _FakeInsertResp(self.response_rows)


class _FakeSupabase:
    def __init__(self, table: _FakeTable) -> None:
        self.table_obj = table
        self.last_table_name: str | None = None

    def table(self, name: str) -> _FakeTable:
        self.last_table_name = name
        return self.table_obj


# Realistic body the mobile client posts on every IntroScreen toggle.
_VALID_PAYLOAD = {
    "clause_id": "kvkk",
    "accepted": True,
    "notice_version": "2026-05-01",
    "consent_version": "1.0",
}


class TestConsentEventRoute(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("app.supabase_client.get_supabase")
    def test_records_event_and_surfaces_inserted_id(self, mock_get_sb) -> None:
        fake_table = _FakeTable(response_rows=[{"id": 4242}])
        mock_get_sb.return_value = _FakeSupabase(fake_table)

        resp = self.client.post(
            "/v1/consent/event",
            json=_VALID_PAYLOAD,
            headers={"X-Device-Id": "device-abc"},
        )

        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["ok"], True)
        self.assertEqual(body["id"], 4242)

        # Inserted row carries the device id from the header, never
        # something parsed from the JSON body — keeps device-spoofing
        # blocked at the boundary.
        self.assertEqual(fake_table.last_payload["device_id"], "device-abc")
        self.assertEqual(fake_table.last_payload["clause_id"], "kvkk")
        self.assertEqual(fake_table.last_payload["accepted"], True)

    @patch("app.supabase_client.get_supabase")
    def test_un_tick_is_recorded_same_as_tick(self, mock_get_sb) -> None:
        fake_table = _FakeTable(response_rows=[{"id": 1}])
        mock_get_sb.return_value = _FakeSupabase(fake_table)

        payload = {**_VALID_PAYLOAD, "accepted": False, "clause_id": "terms"}
        resp = self.client.post(
            "/v1/consent/event",
            json=payload,
            headers={"X-Device-Id": "device-xyz"},
        )

        self.assertEqual(resp.status_code, 201)
        # Critical for KVKK audit: the un-tick is a real event, not a
        # silent no-op. The auditor needs to see the user changed their
        # mind even if they re-ticked before pressing Başla.
        self.assertEqual(fake_table.last_payload["accepted"], False)
        self.assertEqual(fake_table.last_payload["clause_id"], "terms")

    @patch("app.supabase_client.get_supabase")
    def test_each_valid_clause_id_passes(self, mock_get_sb) -> None:
        fake_table = _FakeTable(response_rows=[{"id": 1}])
        mock_get_sb.return_value = _FakeSupabase(fake_table)

        for clause in ("terms", "kvkk", "age"):
            payload = {**_VALID_PAYLOAD, "clause_id": clause}
            resp = self.client.post(
                "/v1/consent/event",
                json=payload,
                headers={"X-Device-Id": "device-1"},
            )
            self.assertEqual(
                resp.status_code,
                201,
                f"clause '{clause}' should be accepted",
            )

    def test_missing_device_id_returns_400(self) -> None:
        resp = self.client.post(
            "/v1/consent/event",
            json=_VALID_PAYLOAD,
            # no X-Device-Id header
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body["detail"]["code"], "missing_device_id")

    def test_invalid_clause_id_returns_422(self) -> None:
        # FastAPI / Pydantic rejects unknown literal values before the
        # route body runs — keeps Supabase from ever seeing garbage.
        bad = {**_VALID_PAYLOAD, "clause_id": "marketing"}
        resp = self.client.post(
            "/v1/consent/event",
            json=bad,
            headers={"X-Device-Id": "device-1"},
        )
        self.assertEqual(resp.status_code, 422)

    @patch("app.supabase_client.get_supabase")
    def test_supabase_exception_returns_503(self, mock_get_sb) -> None:
        # Storage outage shouldn't 200 the request. The mobile client
        # would treat a 200 as "audit recorded" and the user might
        # bypass onboarding without a paper trail.
        sb = MagicMock()
        sb.table.return_value.insert.return_value.execute.side_effect = (
            RuntimeError("supabase down")
        )
        mock_get_sb.return_value = sb

        resp = self.client.post(
            "/v1/consent/event",
            json=_VALID_PAYLOAD,
            headers={"X-Device-Id": "device-1"},
        )

        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertEqual(body["detail"]["code"], "audit_log_unavailable")


if __name__ == "__main__":
    unittest.main()
