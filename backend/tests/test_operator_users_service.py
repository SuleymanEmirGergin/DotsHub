"""Tests for the operator_users service.

Hashing + validation + DB boundary against a chainable Supabase mock.
The auth helper integration (require_admin_or_operator) lives in
test_admin_auth.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import operator_users


# ─── Key generation ──────────────────────────────────────────────────


def test_generate_key_returns_64char_hex_pair():
    plain, h = operator_users.generate_api_key()
    assert len(plain) == 64
    assert all(c in "0123456789abcdef" for c in plain)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_generate_key_two_calls_differ():
    """secrets.token_hex collisions are statistically impossible at
    32 bytes; this test catches a regression that swaps to a
    deterministic source."""
    p1, _ = operator_users.generate_api_key()
    p2, _ = operator_users.generate_api_key()
    assert p1 != p2


def test_hash_api_key_deterministic():
    a = operator_users.hash_api_key("abcd1234")
    b = operator_users.hash_api_key("abcd1234")
    assert a == b
    assert len(a) == 64


def test_hash_changes_with_input():
    a = operator_users.hash_api_key("abcd1234")
    b = operator_users.hash_api_key("abcd1235")
    assert a != b


# ─── Role validation ─────────────────────────────────────────────────


def test_valid_roles_set():
    assert operator_users.VALID_ROLES == {"reviewer", "manager", "admin"}


def test_role_rank_hierarchy():
    """reviewer < manager < admin. require_min_role depends on this."""
    assert operator_users.ROLE_RANK["reviewer"] < operator_users.ROLE_RANK["manager"]
    assert operator_users.ROLE_RANK["manager"] < operator_users.ROLE_RANK["admin"]


# ─── DB boundary ─────────────────────────────────────────────────────


@pytest.fixture
def fake_supabase():
    sb = MagicMock()
    chain = MagicMock()
    sb.table.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.is_.return_value = chain
    chain.maybe_single.return_value = chain
    chain.order.return_value = chain
    return sb, chain


def test_lookup_by_key_short_input_returns_none_no_db(fake_supabase):
    """Malformed header bypasses Supabase round-trip — saves a query
    when someone hits the endpoint without a key."""
    sb, chain = fake_supabase
    chain.execute.side_effect = AssertionError("must not query DB on short key")
    with patch("app.db.supabase", sb):
        assert operator_users.lookup_by_key("") is None
        assert operator_users.lookup_by_key("short") is None


def test_lookup_by_key_hashes_before_query(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data={"id": "OP-1", "email": "x@y.z", "full_name": "X", "role": "reviewer"}
    )
    plain = "a" * 64
    with patch("app.db.supabase", sb):
        out = operator_users.lookup_by_key(plain)
    assert out is not None
    eq_call = chain.eq.call_args.args
    assert eq_call[0] == "api_key_hash"
    # The eq value MUST be the hash, NOT the plaintext.
    assert eq_call[1] == operator_users.hash_api_key(plain)
    assert eq_call[1] != plain


def test_lookup_filters_deactivated(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=None)
    with patch("app.db.supabase", sb):
        operator_users.lookup_by_key("a" * 64)
    chain.is_.assert_called_with("deactivated_at", "null")


def test_lookup_returns_none_on_db_error(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        assert operator_users.lookup_by_key("a" * 64) is None


def test_create_inserts_row_and_returns_plaintext_once(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{
            "id": "OP-NEW",
            "email": "x@y.z",
            "full_name": "X",
            "role": "reviewer",
            "created_at": "2026-04-27T00:00:00Z",
        }]
    )
    with patch("app.db.supabase", sb):
        plain, row = operator_users.create(
            email="X@Y.Z", full_name=" X ", role="reviewer",
        )
    assert plain
    assert len(plain) == 64
    inserted = chain.insert.call_args.args[0]
    # Email lowercased + trimmed; name trimmed.
    assert inserted["email"] == "x@y.z"
    assert inserted["full_name"] == "X"
    # Hash NOT plaintext on the row.
    assert inserted["api_key_hash"] == operator_users.hash_api_key(plain)
    assert "api_key" not in inserted  # never sent plaintext to DB
    assert row["id"] == "OP-NEW"


def test_create_invalid_role_raises_value_error():
    with pytest.raises(ValueError):
        operator_users.create(email="a@b.c", full_name="X", role="god_mode")


def test_create_missing_required_raises():
    with pytest.raises(ValueError):
        operator_users.create(email="", full_name="X", role="reviewer")
    with pytest.raises(ValueError):
        operator_users.create(email="a@b.c", full_name="", role="reviewer")


def test_create_empty_db_response_raises_runtime(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb), pytest.raises(RuntimeError):
        operator_users.create(email="a@b.c", full_name="X", role="reviewer")


def test_list_all_omits_deactivated_by_default(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        operator_users.list_all()
    chain.is_.assert_called_with("deactivated_at", "null")


def test_list_all_include_deactivated_skips_filter(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        operator_users.list_all(include_deactivated=True)
    # is_ filter NOT applied (no call). order called for sort.
    chain.is_.assert_not_called()


def test_update_invalid_role_raises():
    with pytest.raises(ValueError):
        operator_users.update("OP-1", role="ultra")


def test_update_returns_none_on_no_match(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        out = operator_users.update("missing-id", full_name="X")
    assert out is None


def test_update_persists_only_provided_fields(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{"id": "OP-1", "full_name": "Y", "role": "manager"}]
    )
    with patch("app.db.supabase", sb):
        operator_users.update("OP-1", full_name=" Y ", role=None)
    patch_arg = chain.update.call_args.args[0]
    assert patch_arg["full_name"] == "Y"
    assert "role" not in patch_arg
    assert "updated_at" in patch_arg


def test_deactivate_skips_already_deactivated(fake_supabase):
    """The .is_("deactivated_at", "null") filter ensures running
    deactivate twice is a no-op (returns False)."""
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        assert operator_users.deactivate("OP-1") is False
    chain.is_.assert_called_with("deactivated_at", "null")


def test_deactivate_returns_true_on_match(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[{"id": "OP-1"}])
    with patch("app.db.supabase", sb):
        assert operator_users.deactivate("OP-1") is True
