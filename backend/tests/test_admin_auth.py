"""Tests for the unified admin/operator auth helper.

Covers:
  - super-admin path (x-admin-key) and operator path (x-operator-key)
    each succeed
  - role hierarchy enforcement (require_min_role)
  - operator-keyed rate limit applied AFTER auth lookup
  - 401 messages don't leak unknown-vs-deactivated distinction
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import admin_auth, rate_limit
from app.services import operator_users


@pytest.fixture(autouse=True)
def _reset_buckets():
    """The operator rate-limit shares _BUCKETS with admin/default;
    other tests already clear via conftest, but this file's tight
    rate-limit assertions need a guaranteed clean slate."""
    rate_limit._BUCKETS.clear()
    yield
    rate_limit._BUCKETS.clear()


# ─── Super-admin path ────────────────────────────────────────────────


def test_super_admin_passes(monkeypatch):
    monkeypatch.setattr(admin_auth.settings, "ADMIN_API_KEY", "super-secret")
    auth = admin_auth.require_admin_or_operator(
        x_admin_key="super-secret", x_operator_key=None,
    )
    assert auth["is_super_admin"] is True
    assert auth["role"] == "admin"
    assert auth["id"] == "admin_api_key"


def test_super_admin_with_wrong_key_falls_through_to_operator(monkeypatch):
    """A wrong x-admin-key isn't a hard reject — if x-operator-key is
    also set we try that. Lets a misconfigured client (both headers
    set) still authenticate via the operator key."""
    monkeypatch.setattr(admin_auth.settings, "ADMIN_API_KEY", "super-secret")
    op_row = {"id": "OP-1", "email": "x@y.z", "full_name": "X", "role": "manager"}
    with patch.object(operator_users, "lookup_by_key", return_value=op_row):
        auth = admin_auth.require_admin_or_operator(
            x_admin_key="wrong", x_operator_key="a" * 64,
        )
    assert auth["id"] == "OP-1"
    assert auth["role"] == "manager"
    assert auth["is_super_admin"] is False


def test_no_headers_returns_401():
    with pytest.raises(HTTPException) as exc:
        admin_auth.require_admin_or_operator(
            x_admin_key=None, x_operator_key=None,
        )
    assert exc.value.status_code == 401


def test_unknown_operator_key_returns_401():
    with patch.object(operator_users, "lookup_by_key", return_value=None):
        with pytest.raises(HTTPException) as exc:
            admin_auth.require_admin_or_operator(
                x_admin_key=None, x_operator_key="a" * 64,
            )
    assert exc.value.status_code == 401


def test_operator_lookup_returns_normalised_context():
    op_row = {
        "id": "OP-7", "email": "y@y.z",
        "full_name": "Yedi", "role": "reviewer",
    }
    with patch.object(operator_users, "lookup_by_key", return_value=op_row):
        auth = admin_auth.require_admin_or_operator(
            x_admin_key=None, x_operator_key="a" * 64,
        )
    assert auth == {
        "id": "OP-7",
        "name": "Yedi",
        "role": "reviewer",
        "is_super_admin": False,
        "email": "y@y.z",
    }


# ─── Role hierarchy ──────────────────────────────────────────────────


def test_require_min_role_super_admin_always_passes():
    auth = {"is_super_admin": True, "role": "admin"}
    # Even calling with the highest minimum -> passes.
    admin_auth.require_min_role(auth, "admin")


def test_require_min_role_reviewer_blocked_from_manager():
    auth = {"is_super_admin": False, "role": "reviewer"}
    with pytest.raises(HTTPException) as exc:
        admin_auth.require_min_role(auth, "manager")
    assert exc.value.status_code == 403


def test_require_min_role_manager_passes_reviewer_minimum():
    auth = {"is_super_admin": False, "role": "manager"}
    admin_auth.require_min_role(auth, "reviewer")


def test_require_min_role_manager_blocked_from_admin():
    auth = {"is_super_admin": False, "role": "manager"}
    with pytest.raises(HTTPException) as exc:
        admin_auth.require_min_role(auth, "admin")
    assert exc.value.status_code == 403


def test_require_min_role_admin_passes_all():
    auth = {"is_super_admin": False, "role": "admin"}
    for tier in ("reviewer", "manager", "admin"):
        admin_auth.require_min_role(auth, tier)


# ─── Rate limit ──────────────────────────────────────────────────────


def test_operator_rate_limit_per_operator_independent(monkeypatch):
    """Two different operators must NOT share a bucket — quota is
    per-operator-id."""
    monkeypatch.setattr(rate_limit, "OPERATOR_MAX_REQ", 2)

    op1 = {"id": "OP-A", "email": "a@b.c", "full_name": "A", "role": "reviewer"}
    op2 = {"id": "OP-B", "email": "b@b.c", "full_name": "B", "role": "reviewer"}

    # Burn OP-A's quota.
    with patch.object(operator_users, "lookup_by_key", return_value=op1):
        admin_auth.require_admin_or_operator(
            x_admin_key=None, x_operator_key="a" * 64
        )
        admin_auth.require_admin_or_operator(
            x_admin_key=None, x_operator_key="a" * 64
        )
        # Third call must 429.
        with pytest.raises(HTTPException) as exc:
            admin_auth.require_admin_or_operator(
                x_admin_key=None, x_operator_key="a" * 64
            )
        assert exc.value.status_code == 429

    # OP-B still has full quota.
    with patch.object(operator_users, "lookup_by_key", return_value=op2):
        auth = admin_auth.require_admin_or_operator(
            x_admin_key=None, x_operator_key="b" * 64,
        )
    assert auth["id"] == "OP-B"


def test_operator_rate_limit_skipped_for_super_admin(monkeypatch):
    """Super-admin uses the existing IP-keyed admin bucket (middleware-
    enforced); the dependency MUST NOT also charge them against an
    operator bucket."""
    monkeypatch.setattr(admin_auth.settings, "ADMIN_API_KEY", "super-secret")
    monkeypatch.setattr(rate_limit, "OPERATOR_MAX_REQ", 1)

    # 10 super-admin calls in a row -- never 429.
    for _ in range(10):
        auth = admin_auth.require_admin_or_operator(
            x_admin_key="super-secret", x_operator_key=None,
        )
        assert auth["is_super_admin"] is True


def test_rate_limit_includes_retry_after_header():
    """429 response must include Retry-After so clients back off."""
    op = {"id": "OP-X", "email": "x@y.z", "full_name": "X", "role": "reviewer"}
    with patch.object(operator_users, "lookup_by_key", return_value=op), \
            patch.object(rate_limit, "OPERATOR_MAX_REQ", 0):
        # MAX=0 -> first request denied.
        try:
            admin_auth.require_admin_or_operator(
                x_admin_key=None, x_operator_key="a" * 64,
            )
        except HTTPException as exc:
            assert exc.status_code == 429
            assert "Retry-After" in exc.headers
            return
    pytest.fail("expected 429")
