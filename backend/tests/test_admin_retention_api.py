"""Tests for the patient-uploads retention sweep endpoint.

Service-level tests for ``tombstone_expired_uploads`` live in the
existing ``test_patient_uploads_service.py`` (lt + is_ filter
chain). This file covers the HTTP boundary: auth, status codes,
response shape, error -> 500 mapping.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import patient_uploads


_ADMIN_KEY = "test-admin-key"  # matches conftest._STUB_ENV


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_missing_admin_key_returns_401(client):
    resp = client.post("/v1/admin/retention/patient-uploads/sweep")
    assert resp.status_code == 401


def test_wrong_admin_key_returns_401(client):
    resp = client.post(
        "/v1/admin/retention/patient-uploads/sweep",
        headers={"x-admin-key": "wrong"},
    )
    assert resp.status_code == 401


def test_happy_path_returns_count(client):
    with patch.object(
        patient_uploads, "tombstone_expired_uploads", return_value=7,
    ) as mock_sweep:
        resp = client.post(
            "/v1/admin/retention/patient-uploads/sweep",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tombstoned_count"] == 7
    assert "started_at" in body
    assert "processed_at" in body
    mock_sweep.assert_called_once_with(reason="scheduled_retention")


def test_zero_count_returns_200(client):
    """Empty sweep is normal — no expired rows yet, or already-
    tombstoned by a prior run. Cron worker treats 200 with count=0
    as success (not silent skip)."""
    with patch.object(
        patient_uploads, "tombstone_expired_uploads", return_value=0,
    ):
        resp = client.post(
            "/v1/admin/retention/patient-uploads/sweep",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["tombstoned_count"] == 0


def test_db_failure_surfaces_as_500(client):
    """Service returns -1 on DB blip -> endpoint must surface as
    500 so the cron workflow fails and the Slack/Discord webhook
    fires."""
    with patch.object(
        patient_uploads, "tombstone_expired_uploads", return_value=-1,
    ):
        resp = client.post(
            "/v1/admin/retention/patient-uploads/sweep",
            headers={"x-admin-key": _ADMIN_KEY},
        )
    assert resp.status_code == 500
    assert "retention" in resp.json()["detail"].lower()
