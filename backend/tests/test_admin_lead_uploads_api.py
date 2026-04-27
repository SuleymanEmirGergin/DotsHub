"""Tests for the lead↔upload link endpoints (manager+ role gated)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import lead_uploads, operator_users, patient_uploads


_ADMIN_KEY = "test-admin-key"


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _upload_row(asset_id="A-1"):
    """Minimal fake patient_uploads row — get_upload returns this for
    "exists + not tombstoned" precheck."""
    return {
        "asset_id": asset_id,
        "ai_status": "succeeded",
        "deleted_at": None,
    }


# ─── PATCH auth ──────────────────────────────────────────────────────


def test_patch_no_auth_returns_401(client):
    resp = client.patch(
        "/v1/admin/leads/L-1/uploads", json={"asset_ids": []}
    )
    assert resp.status_code == 401


def test_patch_reviewer_role_returns_403(client):
    """Reviewer can review individual uploads but cannot curate the
    lead-level link bag (manager+)."""
    op = {
        "id": "OP-1", "email": "rev@x.tr", "full_name": "R",
        "role": "reviewer",
    }
    with patch.object(operator_users, "lookup_by_key", return_value=op):
        resp = client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-operator-key": "a" * 64},
            json={"asset_ids": []},
        )
    assert resp.status_code == 403


def test_patch_manager_role_passes(client):
    op = {
        "id": "OP-2", "email": "mgr@x.tr", "full_name": "M",
        "role": "manager",
    }
    with patch.object(
        operator_users, "lookup_by_key", return_value=op,
    ), patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        lead_uploads, "replace_links_for_lead",
        return_value={
            "added": [], "removed": [], "kept": [], "current": [],
        },
    ):
        resp = client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-operator-key": "a" * 64},
            json={"asset_ids": []},
        )
    assert resp.status_code == 200


def test_patch_super_admin_passes(client):
    with patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        lead_uploads, "replace_links_for_lead",
        return_value={
            "added": [], "removed": [], "kept": [], "current": [],
        },
    ):
        resp = client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"asset_ids": []},
        )
    assert resp.status_code == 200


# ─── PATCH validation ────────────────────────────────────────────────


def test_patch_unknown_lead_returns_404(client):
    with patch.object(lead_uploads, "lead_exists", return_value=False):
        resp = client.patch(
            "/v1/admin/leads/L-MISSING/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"asset_ids": []},
        )
    assert resp.status_code == 404


def test_patch_unknown_asset_returns_422_atomic(client):
    """If ANY asset_id is unknown / tombstoned, the WHOLE request
    422s and NO links are modified (atomic precheck)."""
    with patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        patient_uploads, "get_upload",
        side_effect=lambda aid: _upload_row(aid) if aid == "A-1" else None,
    ), patch.object(
        lead_uploads, "replace_links_for_lead",
        side_effect=AssertionError("must not run when precheck fails"),
    ):
        resp = client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"asset_ids": ["A-1", "A-MISSING", "A-TOMBSTONED"]},
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "A-MISSING" in detail
    assert "A-TOMBSTONED" in detail


def test_patch_asset_ids_over_cap_returns_422(client):
    """Cap is 100; pathological payload should fail Pydantic validation."""
    resp = client.patch(
        "/v1/admin/leads/L-1/uploads",
        headers={"x-admin-key": _ADMIN_KEY},
        json={"asset_ids": [f"A-{i}" for i in range(101)]},
    )
    assert resp.status_code == 422


# ─── PATCH happy path + linker resolution ────────────────────────────


def test_patch_returns_diff_summary(client):
    with patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        patient_uploads, "get_upload", return_value=_upload_row(),
    ), patch.object(
        lead_uploads, "replace_links_for_lead",
        return_value={
            "added": ["A-3"],
            "removed": ["A-1"],
            "kept": ["A-2"],
            "current": ["A-2", "A-3"],
        },
    ):
        resp = client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"asset_ids": ["A-2", "A-3"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == ["A-3"]
    assert body["removed"] == ["A-1"]
    assert body["kept"] == ["A-2"]
    assert body["current"] == ["A-2", "A-3"]


def test_patch_super_admin_writes_admin_as_linker(client):
    captured = {}

    def _capture(lead_id, asset_ids, *, linked_by_operator_id):
        captured["linked_by_operator_id"] = linked_by_operator_id
        return {"added": [], "removed": [], "kept": [], "current": []}

    with patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        lead_uploads, "replace_links_for_lead", side_effect=_capture,
    ):
        client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"asset_ids": []},
        )
    assert captured["linked_by_operator_id"] == "admin"


def test_patch_operator_writes_email_as_linker(client):
    op = {
        "id": "OP-2", "email": "manager@clinic.tr",
        "full_name": "Manager", "role": "manager",
    }
    captured = {}

    def _capture(lead_id, asset_ids, *, linked_by_operator_id):
        captured["linked_by_operator_id"] = linked_by_operator_id
        return {"added": [], "removed": [], "kept": [], "current": []}

    with patch.object(
        operator_users, "lookup_by_key", return_value=op,
    ), patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        lead_uploads, "replace_links_for_lead", side_effect=_capture,
    ):
        client.patch(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-operator-key": "a" * 64},
            json={"asset_ids": []},
        )
    assert captured["linked_by_operator_id"] == "manager@clinic.tr"


# ─── GET companion ──────────────────────────────────────────────────


def test_get_unknown_lead_returns_404(client):
    with patch.object(lead_uploads, "lead_exists", return_value=False):
        resp = client.get(
            "/v1/admin/leads/L-X/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 404


def test_get_returns_link_rows(client):
    rows = [
        {"id": "LK-1", "lead_id": "L-1", "asset_id": "A-1"},
        {"id": "LK-2", "lead_id": "L-1", "asset_id": "A-2"},
    ]
    with patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        lead_uploads, "list_active_for_lead", return_value=rows,
    ):
        resp = client.get(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_reviewer_can_read(client):
    """Read access on link bag is reviewer-tier (no manager floor on
    GET — same as the upload queue list)."""
    op = {
        "id": "OP-1", "email": "rev@x.tr", "full_name": "R",
        "role": "reviewer",
    }
    with patch.object(
        operator_users, "lookup_by_key", return_value=op,
    ), patch.object(
        lead_uploads, "lead_exists", return_value=True,
    ), patch.object(
        lead_uploads, "list_active_for_lead", return_value=[],
    ):
        resp = client.get(
            "/v1/admin/leads/L-1/uploads",
            headers={"x-operator-key": "a" * 64},
        )
    assert resp.status_code == 200
