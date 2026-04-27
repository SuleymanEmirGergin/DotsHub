"""Tests for GET /v1/admin/me — auth context echo."""
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


def test_no_auth_returns_401(client):
    resp = client.get("/v1/admin/me")
    assert resp.status_code == 401


def test_super_admin_returns_admin_context(client):
    resp = client.get("/v1/admin/me", headers={"x-admin-key": _ADMIN_KEY})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_super_admin"] is True
    assert body["role"] == "admin"
    assert body["id"] == "admin_api_key"
    assert body["name"] == "admin"
    assert body["email"] is None


def test_operator_returns_full_context(client):
    op = {
        "id": "OP-123",
        "email": "doctor@clinic.tr",
        "full_name": "Dr Sample",
        "role": "manager",
    }
    with patch.object(operator_users, "lookup_by_key", return_value=op):
        resp = client.get(
            "/v1/admin/me",
            headers={"x-operator-key": "a" * 64},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "OP-123"
    assert body["name"] == "Dr Sample"
    assert body["role"] == "manager"
    assert body["is_super_admin"] is False
    assert body["email"] == "doctor@clinic.tr"


def test_unknown_operator_returns_401(client):
    with patch.object(operator_users, "lookup_by_key", return_value=None):
        resp = client.get(
            "/v1/admin/me", headers={"x-operator-key": "a" * 64},
        )
    assert resp.status_code == 401


def test_response_shape_only_documented_fields(client):
    """The dashboard caches this response shape; if a field appears
    here it becomes part of the contract. Tripwire so a future
    addition doesn't silently leak (e.g. `api_key_hash`)."""
    resp = client.get("/v1/admin/me", headers={"x-admin-key": _ADMIN_KEY})
    body = resp.json()
    expected_keys = {"id", "name", "role", "is_super_admin", "email"}
    assert set(body.keys()) == expected_keys
