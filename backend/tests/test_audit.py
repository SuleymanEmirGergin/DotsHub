"""Tests for app.audit — WORM audit log writer.

Compliance lineage: docs/DPIA_2026.md:R-10. Schema:
backend/sql/20260427_audit_log.sql.

These tests pin the API surface and the safety invariants:
1. record_event never raises (best-effort write).
2. PII keys in payload are scrubbed and a warning is logged.
3. Common event shapes (data_rights, consent) round-trip.
4. The route layer is wired (data_rights + consent both insert).

The SQL-level WORM enforcement (UPDATE/DELETE triggers) is verified
by the schema file's own structure and via Supabase staging dry-run
— same pattern as test_retention_config.py for the purge SQL.
"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def _mock_supabase_with_capture(captured: list) -> MagicMock:
    """A supabase mock whose .table().insert() captures the row."""
    s = MagicMock()

    def _insert(row):
        captured.append(row)
        execute_mock = MagicMock()
        execute_mock.execute.return_value.data = [
            {"id": len(captured), "created_at": "2026-04-27T10:00:00Z"}
        ]
        return execute_mock

    s.table.return_value.insert.side_effect = _insert
    return s


class AuditModuleTests(unittest.TestCase):
    """Direct tests of app.audit.record_event without HTTP layer."""

    def test_record_event_never_raises_on_supabase_failure(self):
        """Best-effort write — a DB outage must not break the caller."""
        s = MagicMock()
        s.table.return_value.insert.return_value.execute.side_effect = (
            RuntimeError("supabase down")
        )
        with patch("app.db.supabase", s):
            from app.audit import record_event

            try:
                record_event(
                    event_type="test.something",
                    actor_type="system",
                    actor_id="actor-1",
                )
            except Exception as exc:
                self.fail(f"record_event must not raise; got {exc}")

    def test_record_event_inserts_basic_shape(self):
        captured: list = []
        s = _mock_supabase_with_capture(captured)
        with patch("app.db.supabase", s):
            from app.audit import record_event

            record_event(
                event_type="data_rights.session_tombstoned",
                actor_type="user",
                actor_id="device-abc",
                target_id="session-xyz",
                payload={"derived_deleted": {"events": 5}},
                ip_hash="hash-123",
            )

        self.assertEqual(len(captured), 1)
        row = captured[0]
        self.assertEqual(row["event_type"], "data_rights.session_tombstoned")
        self.assertEqual(row["actor_type"], "user")
        self.assertEqual(row["actor_id"], "device-abc")
        self.assertEqual(row["target_id"], "session-xyz")
        self.assertEqual(row["severity"], "info")
        self.assertEqual(row["payload"], {"derived_deleted": {"events": 5}})
        self.assertEqual(row["ip_hash"], "hash-123")

    def test_record_event_scrubs_pii_keys(self):
        """input_text, email, comment etc. must NOT make it to the row."""
        captured: list = []
        s = _mock_supabase_with_capture(captured)
        with patch("app.db.supabase", s):
            from app.audit import record_event

            with self.assertLogs("app.audit", level="WARNING") as cm:
                record_event(
                    event_type="test.pii_attempt",
                    actor_type="system",
                    payload={
                        "safe_count": 3,
                        "input_text": "user typed something private",
                        "email": "user@example.com",
                        "version": "v1.0",
                    },
                )

        # PII keys are gone; safe ones survive.
        row = captured[0]
        self.assertNotIn("input_text", row["payload"])
        self.assertNotIn("email", row["payload"])
        self.assertEqual(row["payload"]["safe_count"], 3)
        self.assertEqual(row["payload"]["version"], "v1.0")

        # Each scrubbed key produced a warning — visible in Sentry.
        scrub_log_messages = [
            r.message for r in cm.records if "pii_scrubbed" in r.message
        ]
        self.assertGreaterEqual(len(scrub_log_messages), 2)

    def test_record_event_with_empty_payload_is_ok(self):
        captured: list = []
        s = _mock_supabase_with_capture(captured)
        with patch("app.db.supabase", s):
            from app.audit import record_event

            record_event(event_type="test.no_payload", actor_type="system")

        row = captured[0]
        self.assertEqual(row["payload"], {})


class AuditWiredFromDataRightsTests(unittest.TestCase):
    """Verify DELETE /v1/me/sessions/{id} produces an audit row."""

    def test_delete_session_emits_audit_event(self):
        # Two supabase consumers in this flow:
        #   - data_rights (read existing session, delete derived,
        #     update tombstone)
        #   - audit (insert audit_log row)
        # Same mock serves both because Supabase client is a single
        # singleton at app.db.supabase.
        captured_audit: list = []
        s = MagicMock()

        # session lookup: returns a live row (not yet tombstoned).
        existing_data = MagicMock()
        existing_data.data = {"id": "sess-1", "deleted_at": None}
        s.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value = existing_data

        # delete and update chains — return arbitrary data.
        s.table.return_value.delete.return_value.eq.return_value.execute\
            .return_value.data = []
        s.table.return_value.update.return_value.eq.return_value.execute\
            .return_value.data = []

        # audit_log insert — capture.
        original_insert = s.table.return_value.insert

        def _insert_capture(row):
            if row.get("event_type"):
                captured_audit.append(row)
            return original_insert.return_value

        s.table.return_value.insert.side_effect = _insert_capture

        with patch("app.db.supabase", s):
            with TestClient(app) as client:
                # 32-char min length per route validator.
                response = client.delete(
                    "/v1/me/sessions/11111111-1111-1111-1111-111111111111"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured_audit), 1)
        ev = captured_audit[0]
        self.assertEqual(ev["event_type"], "data_rights.session_tombstoned")
        self.assertEqual(ev["actor_type"], "user")
        self.assertEqual(
            ev["target_id"], "11111111-1111-1111-1111-111111111111"
        )
        self.assertIn("derived_deleted", ev["payload"])
        self.assertEqual(ev["payload"]["deleted_reason"], "user_request")


class AuditWiredFromConsentTests(unittest.TestCase):
    """Verify POST /v1/consent produces a paired audit row."""

    def test_post_consent_emits_audit_event(self):
        captured_inserts: list = []
        s = MagicMock()

        def _insert_capture(row):
            captured_inserts.append(row)
            execute_mock = MagicMock()
            execute_mock.execute.return_value.data = [
                {"id": len(captured_inserts), "created_at": "2026-04-27T10:00:00Z"}
            ]
            return execute_mock

        s.table.return_value.insert.side_effect = _insert_capture

        with patch("app.db.supabase", s):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "health_data_processing",
                        "consent_version": "v1.0",
                        "granted": True,
                        "locale": "tr",
                        "device_id": "device-audit-1",
                    },
                )

        self.assertEqual(response.status_code, 201)
        # Exactly two inserts: consent_records + audit_log. The
        # ordering is consent_records first (route logic), then
        # audit_log (post-success).
        self.assertEqual(len(captured_inserts), 2)
        consent_row, audit_row = captured_inserts

        # consent_records row carries the actual data.
        self.assertEqual(consent_row["consent_type"], "health_data_processing")
        self.assertTrue(consent_row["granted"])

        # audit_log row carries the metadata + cross-link.
        self.assertEqual(audit_row["event_type"], "consent.recorded")
        self.assertEqual(audit_row["actor_type"], "user")
        self.assertEqual(audit_row["actor_id"], "device-audit-1")
        self.assertEqual(audit_row["payload"]["consent_type"], "health_data_processing")
        self.assertEqual(audit_row["payload"]["granted"], True)
        # Cross-link: consent_records.id is captured in audit payload.
        self.assertIn("consent_records_id", audit_row["payload"])

    def test_consent_audit_failure_does_not_break_consent_post(self):
        """If audit insert fails, the consent POST must still return 201
        — audit is defense-in-depth, not an availability gate."""
        s = MagicMock()
        call_count = {"n": 0}

        def _insert_or_fail(row):
            call_count["n"] += 1
            execute_mock = MagicMock()
            if call_count["n"] == 2:
                # Second insert is the audit row — make it fail.
                execute_mock.execute.side_effect = RuntimeError("audit table down")
            else:
                execute_mock.execute.return_value.data = [
                    {"id": 1, "created_at": "2026-04-27T10:00:00Z"}
                ]
            return execute_mock

        s.table.return_value.insert.side_effect = _insert_or_fail

        with patch("app.db.supabase", s):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/consent",
                    json={
                        "consent_type": "terms_general",
                        "consent_version": "v1.0",
                        "granted": True,
                        "device_id": "device-audit-2",
                    },
                )

        # 201 even though audit row failed.
        self.assertEqual(response.status_code, 201)


if __name__ == "__main__":
    unittest.main()
