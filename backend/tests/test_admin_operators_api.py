"""Tests for the operator management endpoints (super-admin gated)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import operator_users


_ADMIN_KEY = "test-admin-key"


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# ─── Auth ────────────────────────────────────────────────────────────


def test_create_requires_admin_key(client):
    resp = client.post(
        "/v1/admin/operators",
        json={"email": "a@b.c", "full_name": "X", "role": "reviewer"},
    )
    assert resp.status_code == 401


def test_list_requires_admin_key(client):
    resp = client.get("/v1/admin/operators")
    assert resp.status_code == 401


def test_operator_key_cannot_manage_operators(client):
    """Operator-tier keys MUST NOT be allowed to provision other
    operators — credential blast radius cap (an operator key leak
    can do operator-level damage but never escalate to provisioning)."""
    op = {
        "id": "OP-X", "email": "x@y.z", "full_name": "X",
        "role": "admin",  # even admin role on operator tier — still blocked
    }
    with patch.object(operator_users, "lookup_by_key", return_value=op):
        resp = client.post(
            "/v1/admin/operators",
            headers={"x-operator-key": "a" * 64},
            json={
                "email": "new@op.z", "full_name": "Y", "role": "reviewer"
            },
        )
    assert resp.status_code == 401


# ─── Create ──────────────────────────────────────────────────────────


def test_create_returns_plaintext_key_once(client):
    fake_row = {
        "id": "OP-NEW",
        "email": "x@y.z",
        "full_name": "X",
        "role": "reviewer",
        "created_at": "2026-04-27T00:00:00Z",
    }
    with patch.object(
        operator_users, "create",
        return_value=("a" * 64, fake_row),
    ):
        resp = client.post(
            "/v1/admin/operators",
            headers={"x-admin-key": _ADMIN_KEY},
            json={
                "email": "x@y.z", "full_name": "X", "role": "reviewer",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"] == "a" * 64
    assert body["id"] == "OP-NEW"
    assert body["role"] == "reviewer"


def test_create_invalid_role_returns_422(client):
    resp = client.post(
        "/v1/admin/operators",
        headers={"x-admin-key": _ADMIN_KEY},
        json={"email": "x@y.z", "full_name": "X", "role": "god_mode"},
    )
    assert resp.status_code == 422


def test_create_invalid_email_returns_422(client):
    resp = client.post(
        "/v1/admin/operators",
        headers={"x-admin-key": _ADMIN_KEY},
        json={"email": "not-an-email", "full_name": "X", "role": "reviewer"},
    )
    assert resp.status_code == 422


def test_create_email_collision_returns_409(client):
    """A live operator with the same email -> 409 (prompt operator
    to deactivate first)."""
    with patch.object(
        operator_users, "create",
        side_effect=Exception("duplicate key value violates unique constraint"),
    ):
        resp = client.post(
            "/v1/admin/operators",
            headers={"x-admin-key": _ADMIN_KEY},
            json={
                "email": "x@y.z", "full_name": "X", "role": "reviewer",
            },
        )
    assert resp.status_code == 409
    assert "deactivate" in resp.json()["detail"]


# ─── List ────────────────────────────────────────────────────────────


def test_list_returns_rows_without_api_key(client):
    """Listing must NEVER include api_key or api_key_hash even though
    the service column projection already drops them — defence in
    depth via Pydantic OperatorRow shape."""
    rows = [
        {
            "id": "OP-1", "email": "a@b.c", "full_name": "Alpha",
            "role": "reviewer",
            "created_at": "2026-04-27T00:00:00Z",
        },
        {
            "id": "OP-2", "email": "b@b.c", "full_name": "Beta",
            "role": "manager",
            "created_at": "2026-04-27T00:00:00Z",
        },
    ]
    with patch.object(operator_users, "list_all", return_value=rows):
        resp = client.get(
            "/v1/admin/operators", headers={"x-admin-key": _ADMIN_KEY}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    for row in body:
        assert "api_key" not in row
        assert "api_key_hash" not in row


def test_list_include_deactivated_query_string(client):
    """The query-string flag flows through to the service call."""
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return []

    with patch.object(operator_users, "list_all", side_effect=_capture):
        client.get(
            "/v1/admin/operators?include_deactivated=true",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert captured == {"include_deactivated": True}


# ─── Update ──────────────────────────────────────────────────────────


def test_update_invalid_role_returns_422(client):
    resp = client.patch(
        "/v1/admin/operators/OP-1",
        headers={"x-admin-key": _ADMIN_KEY},
        json={"role": "wrong"},
    )
    assert resp.status_code == 422


def test_update_empty_body_returns_422(client):
    """Both fields None -> 422 (caller must specify what to change)."""
    resp = client.patch(
        "/v1/admin/operators/OP-1",
        headers={"x-admin-key": _ADMIN_KEY},
        json={},
    )
    assert resp.status_code == 422


def test_update_unknown_id_returns_404(client):
    with patch.object(operator_users, "update", return_value=None):
        resp = client.patch(
            "/v1/admin/operators/OP-MISSING",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"role": "manager"},
        )
    assert resp.status_code == 404


def test_update_happy_path(client):
    fake = {
        "id": "OP-1", "email": "x@y.z", "full_name": "Renamed",
        "role": "manager", "created_at": "2026-04-27T00:00:00Z",
    }
    with patch.object(operator_users, "update", return_value=fake):
        resp = client.patch(
            "/v1/admin/operators/OP-1",
            headers={"x-admin-key": _ADMIN_KEY},
            json={"full_name": "Renamed", "role": "manager"},
        )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed"
    assert resp.json()["role"] == "manager"


# ─── Deactivate ──────────────────────────────────────────────────────


def test_deactivate_returns_204_on_success(client):
    with patch.object(operator_users, "deactivate", return_value=True):
        resp = client.delete(
            "/v1/admin/operators/OP-1",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 204


def test_deactivate_returns_404_when_already_deactivated(client):
    with patch.object(operator_users, "deactivate", return_value=False):
        resp = client.delete(
            "/v1/admin/operators/OP-1",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 404
