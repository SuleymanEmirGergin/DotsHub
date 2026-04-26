"""Tests for the operator upload review queue (GET /v1/admin/uploads).

Auth, filter / pagination shape, tombstone visibility contract.
Service-level filter chain assertions live in
test_patient_uploads_service.py (added below).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import operator_users, patient_uploads


_ADMIN_KEY = "test-admin-key"


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _row(**overrides):
    """Minimal patient_uploads row shape — fields the response surfaces."""
    base = {
        "asset_id": "A1",
        "session_id": "S1",
        "ai_status": "succeeded",
        "ai_provider": "moondream",
        "ai_result_text": "norwood:3",
        "ai_error": None,
        "upload_kind": "image",
        "content_type": "image/png",
        "size_bytes": 1024,
        "consent_to_process": True,
        "expires_at": "2026-05-27T00:00:00Z",
        "created_at": "2026-04-27T00:00:00Z",
        "processed_at": "2026-04-27T00:00:05Z",
        "deleted_at": None,
    }
    base.update(overrides)
    return base


# ─── Auth ────────────────────────────────────────────────────────────


def test_no_auth_returns_401(client):
    resp = client.get("/v1/admin/uploads")
    assert resp.status_code == 401


def test_super_admin_passes(client):
    with patch.object(
        patient_uploads, "list_for_review", return_value=([_row()], 1),
    ):
        resp = client.get(
            "/v1/admin/uploads", headers={"x-admin-key": _ADMIN_KEY}
        )
    assert resp.status_code == 200


def test_operator_reviewer_role_passes(client):
    """Lowest-tier operator can read the queue (any role >= reviewer)."""
    op = {
        "id": "OP-1", "email": "x@y.z", "full_name": "X",
        "role": "reviewer",
    }
    with patch.object(operator_users, "lookup_by_key", return_value=op), \
            patch.object(
                patient_uploads, "list_for_review",
                return_value=([_row()], 1),
            ):
        resp = client.get(
            "/v1/admin/uploads",
            headers={"x-operator-key": "a" * 64},
        )
    assert resp.status_code == 200


# ─── Filter validation ───────────────────────────────────────────────


def test_invalid_ai_status_returns_422(client):
    resp = client.get(
        "/v1/admin/uploads?ai_status=garbage",
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


def test_invalid_kind_returns_422(client):
    resp = client.get(
        "/v1/admin/uploads?kind=ply_3d",
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


def test_limit_above_cap_returns_422(client):
    resp = client.get(
        "/v1/admin/uploads?limit=999",
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


def test_offset_negative_returns_422(client):
    resp = client.get(
        "/v1/admin/uploads?offset=-1",
        headers={"x-admin-key": _ADMIN_KEY},
    )
    assert resp.status_code == 422


# ─── Filter forwarding ───────────────────────────────────────────────


def test_filter_kwargs_forwarded(client):
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return [], 0

    with patch.object(patient_uploads, "list_for_review", side_effect=_capture):
        resp = client.get(
            "/v1/admin/uploads"
            "?ai_status=failed&kind=image&session_id=S1"
            "&created_after=2026-04-01T00:00:00Z"
            "&created_before=2026-04-30T00:00:00Z"
            "&include_tombstoned=true&limit=25&offset=10",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert captured["ai_status"] == "failed"
    assert captured["kind"] == "image"
    assert captured["session_id"] == "S1"
    assert captured["created_after"] == "2026-04-01T00:00:00Z"
    assert captured["created_before"] == "2026-04-30T00:00:00Z"
    assert captured["include_tombstoned"] is True
    assert captured["limit"] == 25
    assert captured["offset"] == 10


def test_default_include_tombstoned_false(client):
    """Tombstoned hidden by default — KVKK contract: deleted means
    deleted, even from operator dashboards. Must be explicit opt-in."""
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return [], 0

    with patch.object(patient_uploads, "list_for_review", side_effect=_capture):
        client.get("/v1/admin/uploads", headers={"x-admin-key": _ADMIN_KEY})
    assert captured["include_tombstoned"] is False


# ─── Response shape ──────────────────────────────────────────────────


def test_response_has_pagination_envelope(client):
    rows = [_row(asset_id=f"A{i}") for i in range(3)]
    with patch.object(
        patient_uploads, "list_for_review", return_value=(rows, 42),
    ):
        resp = client.get(
            "/v1/admin/uploads?limit=3&offset=0",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    body = resp.json()
    assert body["total"] == 42
    assert body["limit"] == 3
    assert body["offset"] == 0
    assert len(body["items"]) == 3


# ─── PATCH /v1/admin/uploads/{asset_id}/review ──────────────────────


def test_review_no_auth_returns_401(client):
    resp = client.patch(
        "/v1/admin/uploads/A1/review",
        json={"review_status": "approved"},
    )
    assert resp.status_code == 401


def test_review_invalid_status_returns_422(client):
    resp = client.patch(
        "/v1/admin/uploads/A1/review",
        headers={"x-admin-key": _ADMIN_KEY},
        json={"review_status": "later_maybe"},
    )
    assert resp.status_code == 422


def test_review_notes_over_cap_returns_422(client):
    resp = client.patch(
        "/v1/admin/uploads/A1/review",
        headers={"x-admin-key": _ADMIN_KEY},
        json={
            "review_status": "approved",
            "reviewer_notes": "x" * 5000,  # cap is 2000
        },
    )
    assert resp.status_code == 422


def test_review_unknown_asset_returns_404(client):
    with patch.object(
        patient_uploads, "set_review_state", return_value=None,
    ):
        resp = client.patch(
            "/v1/admin/uploads/missing/review",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"review_status": "approved"},
        )
    assert resp.status_code == 404


def test_review_super_admin_writes_admin_as_reviewer(client):
    captured = {}

    def _capture(asset_id, **kwargs):
        captured["asset_id"] = asset_id
        captured.update(kwargs)
        return _row(
            review_status=kwargs["review_status"],
            reviewed_by=kwargs["reviewed_by"],
            reviewer_notes=kwargs["reviewer_notes"],
        )

    with patch.object(
        patient_uploads, "set_review_state", side_effect=_capture,
    ):
        resp = client.patch(
            "/v1/admin/uploads/A1/review",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"review_status": "approved", "reviewer_notes": "looks good"},
        )
    assert resp.status_code == 200
    assert captured["reviewed_by"] == "admin"
    assert captured["review_status"] == "approved"
    assert captured["reviewer_notes"] == "looks good"


def test_review_operator_writes_email_as_reviewer(client):
    """Operator-tier auth — reviewed_by gets the operator's email so
    the audit trail names the human reviewer (not just 'admin')."""
    op = {
        "id": "OP-1", "email": "doctor@clinic.tr",
        "full_name": "Dr Sample", "role": "reviewer",
    }
    captured = {}

    def _capture(asset_id, **kwargs):
        captured.update(kwargs)
        return _row(reviewed_by=kwargs["reviewed_by"])

    with patch.object(
        operator_users, "lookup_by_key", return_value=op,
    ), patch.object(
        patient_uploads, "set_review_state", side_effect=_capture,
    ):
        resp = client.patch(
            "/v1/admin/uploads/A1/review",
            headers={"x-operator-key": "a" * 64},
            json={"review_status": "rejected"},
        )
    assert resp.status_code == 200
    assert captured["reviewed_by"] == "doctor@clinic.tr"


def test_review_state_reversible_through_endpoint(client):
    """Operator can move pending_review -> approved -> rejected ->
    needs_followup -> pending_review without 4xx. Each call is
    independent; the service decides nothing about which transition
    is allowed."""
    state_history = []

    def _capture(asset_id, **kwargs):
        state_history.append(kwargs["review_status"])
        return _row(review_status=kwargs["review_status"])

    with patch.object(
        patient_uploads, "set_review_state", side_effect=_capture,
    ):
        for status in ("approved", "rejected", "needs_followup", "pending_review"):
            resp = client.patch(
                "/v1/admin/uploads/A1/review",
                headers={"x-admin-key": _ADMIN_KEY},
                json={"review_status": status},
            )
            assert resp.status_code == 200
    assert state_history == [
        "approved", "rejected", "needs_followup", "pending_review",
    ]


def test_total_falls_back_to_len_when_count_missing(client):
    """If supabase doesn't return a count (older client / wrapped
    response), the route falls back to len(rows) so the dashboard
    still shows a non-zero total when there's data."""
    rows = [_row(), _row(asset_id="A2")]
    with patch.object(
        patient_uploads, "list_for_review", return_value=(rows, 0),
    ):
        resp = client.get(
            "/v1/admin/uploads", headers={"x-admin-key": _ADMIN_KEY}
        )
    assert resp.json()["total"] == 2
