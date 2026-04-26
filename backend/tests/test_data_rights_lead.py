"""DELETE /v1/me/leads/{lead_id} — KVKK silme hakkı for health-tourism leads.

Routes the user-facing delete to lead_repository.soft_delete which
nulls contact + notes and stamps deleted_at — the row stays for the
5-year regulator-mandated retention window.

Tests cover:
    - 200 happy path (lead exists, soft_delete succeeds)
    - 200 already-deleted no-op (idempotency)
    - 404 when the lead_id doesn't exist
    - 400 on malformed lead_id
    - 500 when soft_delete fails after the row was found
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import lead_repository


class DeleteMyLeadTests(unittest.TestCase):
    def test_happy_path_returns_tombstoned(self):
        with patch.object(
            lead_repository, "get",
            return_value={"id": "L1", "is_deleted": False},
        ), patch.object(
            lead_repository, "soft_delete", return_value=True,
        ) as soft_delete_mock:
            with TestClient(app) as client:
                # 36-char UUID-like length passes the malformed check.
                r = client.delete(
                    "/v1/me/leads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["tombstoned"])
        soft_delete_mock.assert_called_once()

    def test_already_deleted_returns_idempotent_noop(self):
        """Re-calling on a tombstoned lead must NOT call soft_delete
        again — idempotency is the contract clients can rely on."""
        with patch.object(
            lead_repository, "get",
            return_value={"id": "L1", "is_deleted": True},
        ), patch.object(
            lead_repository, "soft_delete", return_value=True,
        ) as soft_delete_mock:
            with TestClient(app) as client:
                r = client.delete(
                    "/v1/me/leads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["already_deleted"])
        # No second delete attempt.
        soft_delete_mock.assert_not_called()

    def test_unknown_lead_id_returns_404(self):
        with patch.object(lead_repository, "get", return_value=None):
            with TestClient(app) as client:
                r = client.delete(
                    "/v1/me/leads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                )
        self.assertEqual(r.status_code, 404)

    def test_malformed_id_returns_400(self):
        with TestClient(app) as client:
            r = client.delete("/v1/me/leads/short")
        self.assertEqual(r.status_code, 400)

    def test_soft_delete_failure_after_found_returns_500(self):
        """The lead exists but the UPDATE write failed — surface 500
        so the user can retry, rather than silently 200'ing."""
        with patch.object(
            lead_repository, "get",
            return_value={"id": "L1", "is_deleted": False},
        ), patch.object(
            lead_repository, "soft_delete", return_value=False,
        ):
            with TestClient(app) as client:
                r = client.delete(
                    "/v1/me/leads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                )
        self.assertEqual(r.status_code, 500)


if __name__ == "__main__":
    unittest.main()
