"""Tests for POST /v1/consent and GET /v1/consent.

KVKK Md.6(2) + GDPR Art.9(2)(a) explicit consent audit trail.
Schema: backend/sql/20260427_consent_records.sql.

These tests cover the route surface — Pydantic validation, Supabase
insert/read shape, error paths. They mock the supabase client because
the route layer is what we own; the SQL is verified separately via
staging dry-run (no real-DB CI in this project, same constraint as
test_retention_config.py).
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def _mock_insert_returning(rows: list[dict]) -> MagicMock:
    """A supabase mock where .table().insert().execute() returns rows."""
    s = MagicMock()
    s.table.return_value.insert.return_value.execute.return_value.data = rows
    return s


def _mock_select_returning(rows: list[dict]) -> MagicMock:
    """A supabase mock where the GET chain ends with rows.

    The GET chain is: table().select().eq().eq().order().limit().execute()
    MagicMock auto-chains, so we just set the terminal `.data`.
    """
    s = MagicMock()
    s.table.return_value.select.return_value.eq.return_value.eq.return_value\
        .order.return_value.limit.return_value.execute.return_value.data = rows
    return s


class ConsentPostTests(unittest.TestCase):
    def test_post_201_with_valid_grant(self):
        mock_db = _mock_insert_returning(
            [{"id": 42, "created_at": "2026-04-27T10:00:00Z"}]
        )
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "health_data_processing",
                        "consent_version": "v1.0",
                        "granted": True,
                        "locale": "tr",
                        "device_id": "device-abc",
                    },
                )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["id"], 42)
        self.assertEqual(body["granted_at"], "2026-04-27T10:00:00Z")

    def test_post_201_with_withdrawal(self):
        """granted=false is also a valid record (audit trail)."""
        mock_db = _mock_insert_returning([{"id": 7, "created_at": "2026-04-27T11:00:00Z"}])
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "health_data_processing",
                        "consent_version": "v1.0",
                        "granted": False,
                        "device_id": "device-abc",
                    },
                )
        self.assertEqual(response.status_code, 201)

    def test_post_422_unknown_consent_type(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/consent",
                json={
                    "consent_type": "rogue_type",
                    "consent_version": "v1.0",
                    "granted": True,
                    "device_id": "device-abc",
                },
            )
        self.assertEqual(response.status_code, 422)

    def test_post_422_when_neither_device_nor_session(self):
        """At least one identifier must pin the consent to a known actor."""
        with TestClient(app) as client:
            response = client.post(
                "/v1/consent",
                json={
                    "consent_type": "terms_general",
                    "consent_version": "v1.0",
                    "granted": True,
                },
            )
        self.assertEqual(response.status_code, 422)

    def test_post_422_when_consent_version_missing(self):
        with TestClient(app) as client:
            response = client.post(
                "/v1/consent",
                json={
                    "consent_type": "terms_general",
                    "granted": True,
                    "device_id": "device-abc",
                },
            )
        self.assertEqual(response.status_code, 422)

    def test_post_session_id_only_is_accepted(self):
        """A consent collected mid-session (no device_id known yet) is valid."""
        mock_db = _mock_insert_returning([{"id": 1, "created_at": "2026-04-27T12:00:00Z"}])
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "summary_email",
                        "consent_version": "v1.0",
                        "granted": True,
                        "session_id": "11111111-1111-1111-1111-111111111111",
                    },
                )
        self.assertEqual(response.status_code, 201)

    def test_post_503_when_supabase_raises(self):
        """Persist failure surfaces a 503 with a typed error code so the
        mobile retry path can branch on it."""
        s = MagicMock()
        s.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
            "supabase down"
        )
        with patch("app.db.supabase", s):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "health_data_processing",
                        "consent_version": "v1.0",
                        "granted": True,
                        "device_id": "device-abc",
                    },
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"], "CONSENT_PERSIST_FAILED"
        )

    def test_post_inserts_notice_version_default(self):
        """If notice_version is omitted, the route fills it from settings."""
        mock_db = _mock_insert_returning([{"id": 99, "created_at": "2026-04-27T13:00:00Z"}])
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "terms_general",
                        "consent_version": "v1.0",
                        "granted": True,
                        "device_id": "device-abc",
                    },
                )
        # Inspect the row that was passed to .insert(...)
        insert_args = mock_db.table.return_value.insert.call_args
        row = insert_args.args[0]
        self.assertIsNotNone(row.get("notice_version"))
        # Default comes from settings.PRIVACY_NOTICE_VERSION
        self.assertTrue(row["notice_version"].startswith("v"))


class ConsentGetTests(unittest.TestCase):
    def test_get_returns_latest_state(self):
        mock_db = _mock_select_returning(
            [
                {
                    "granted": True,
                    "consent_version": "v1.0",
                    "notice_version": "v0.2",
                    "locale": "tr",
                    "created_at": "2026-04-27T10:00:00Z",
                }
            ]
        )
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                response = client.get(
                    "/v1/consent",
                    params={
                        "device_id": "device-abc",
                        "consent_type": "health_data_processing",
                    },
                )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["granted"])
        self.assertEqual(body["consent_version"], "v1.0")
        self.assertEqual(body["notice_version"], "v0.2")
        self.assertEqual(body["locale"], "tr")

    def test_get_404_when_no_record(self):
        mock_db = _mock_select_returning([])
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                response = client.get(
                    "/v1/consent",
                    params={
                        "device_id": "fresh-device",
                        "consent_type": "health_data_processing",
                    },
                )
        self.assertEqual(response.status_code, 404)

    def test_get_400_unknown_consent_type(self):
        with TestClient(app) as client:
            response = client.get(
                "/v1/consent",
                params={"device_id": "device-abc", "consent_type": "rogue_type"},
            )
        self.assertEqual(response.status_code, 400)

    def test_get_422_when_device_id_missing(self):
        with TestClient(app) as client:
            response = client.get(
                "/v1/consent",
                params={"consent_type": "health_data_processing"},
            )
        self.assertEqual(response.status_code, 422)

    def test_get_503_when_supabase_raises(self):
        s = MagicMock()
        s.table.return_value.select.return_value.eq.return_value.eq.return_value\
            .order.return_value.limit.return_value.execute.side_effect = RuntimeError(
                "db down"
            )
        with patch("app.db.supabase", s):
            with TestClient(app) as client:
                response = client.get(
                    "/v1/consent",
                    params={
                        "device_id": "device-abc",
                        "consent_type": "health_data_processing",
                    },
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "CONSENT_READ_FAILED")


class ConsentAuditTrailTests(unittest.TestCase):
    """Invariants the route layer guarantees independent of DB schema."""

    def test_post_never_calls_update(self):
        """Audit trail invariant: route never UPDATEs. KVKK Md.12 + GDPR
        Art.7(1) — controller must demonstrate consent was given.
        Mutation would destroy the audit history."""
        mock_db = _mock_insert_returning([{"id": 1, "created_at": "2026-04-27T14:00:00Z"}])
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "terms_general",
                        "consent_version": "v1.0",
                        "granted": True,
                        "device_id": "device-abc",
                    },
                )
        # Walk the call tree — only `insert` may have been called on the
        # consent_records table.
        for call in mock_db.table.return_value.method_calls:
            method_name = call[0]
            if method_name in ("update", "upsert", "delete"):
                self.fail(
                    f"consent route used forbidden mutation '{method_name}' "
                    "— audit trail must be append-only"
                )

    def test_post_records_ip_hash_not_raw_ip(self):
        """We hash the client IP before storing — never the raw value."""
        mock_db = _mock_insert_returning([{"id": 1, "created_at": "2026-04-27T15:00:00Z"}])
        with patch("app.db.supabase", mock_db):
            with TestClient(app) as client:
                client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "terms_general",
                        "consent_version": "v1.0",
                        "granted": True,
                        "device_id": "device-abc",
                    },
                )
        insert_args = mock_db.table.return_value.insert.call_args
        row = insert_args.args[0]
        ip_hash_value = row.get("ip_hash")
        # Either None (no client) or a hash — but MUST NOT look like
        # an IPv4/IPv6 address.
        if ip_hash_value is not None:
            self.assertNotIn(".", ip_hash_value)  # no IPv4 dotted quads
            self.assertNotIn(":", ip_hash_value)  # no IPv6 colons


if __name__ == "__main__":
    unittest.main()
