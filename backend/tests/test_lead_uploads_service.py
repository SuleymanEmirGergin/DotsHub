"""Tests for the lead_uploads service module.

Diff-based replace semantics + lookup helpers + KVKK-aware (links
themselves carry no PII; tombstone just clears the link, never
mutates upstream tables).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import lead_uploads


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
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.maybe_single.return_value = chain
    return sb, chain


# ─── lead_exists ─────────────────────────────────────────────────────


def test_lead_exists_true_when_row_present(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data={"id": "L-1"})
    with patch("app.db.supabase", sb):
        assert lead_uploads.lead_exists("L-1") is True


def test_lead_exists_false_when_no_row(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=None)
    with patch("app.db.supabase", sb):
        assert lead_uploads.lead_exists("L-X") is False


def test_lead_exists_false_on_db_blip(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        assert lead_uploads.lead_exists("L-1") is False


# ─── list_active_for_lead ───────────────────────────────────────────


def test_list_active_filters_tombstoned(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        lead_uploads.list_active_for_lead("L-1")
    chain.is_.assert_called_with("deleted_at", "null")


def test_list_active_returns_rows(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[
            {"id": "LK-1", "lead_id": "L-1", "asset_id": "A-1"},
            {"id": "LK-2", "lead_id": "L-1", "asset_id": "A-2"},
        ]
    )
    with patch("app.db.supabase", sb):
        out = lead_uploads.list_active_for_lead("L-1")
    assert len(out) == 2


def test_list_active_db_blip_returns_empty(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.side_effect = ConnectionError("supabase down")
    with patch("app.db.supabase", sb):
        assert lead_uploads.list_active_for_lead("L-1") == []


# ─── replace_links_for_lead ─────────────────────────────────────────


def _diff_setup(current_links, fake_sb):
    """Wire list_active_for_lead to return the given current links."""
    sb, chain = fake_sb
    # First execute() call (list_active) returns current_links.
    # Subsequent calls (update for tombstone, insert for adds) return
    # a generic ok payload.
    chain.execute.side_effect = [
        MagicMock(data=current_links),
        MagicMock(data=[]),
        MagicMock(data=[]),
        MagicMock(data=[]),
    ]


def test_replace_diff_added_only(fake_supabase):
    """Empty current state -> all desired ids end up in 'added'."""
    sb, chain = fake_supabase
    _diff_setup([], (sb, chain))
    with patch("app.db.supabase", sb):
        diff = lead_uploads.replace_links_for_lead(
            "L-1", ["A-1", "A-2"],
            linked_by_operator_id="ops@x.tr",
        )
    assert diff["added"] == ["A-1", "A-2"]
    assert diff["removed"] == []
    assert diff["kept"] == []
    assert diff["current"] == ["A-1", "A-2"]


def test_replace_diff_removed_only(fake_supabase):
    """Empty desired -> every current link goes to 'removed'."""
    sb, chain = fake_supabase
    _diff_setup(
        [
            {"id": "LK-1", "asset_id": "A-1"},
            {"id": "LK-2", "asset_id": "A-2"},
        ],
        (sb, chain),
    )
    with patch("app.db.supabase", sb):
        diff = lead_uploads.replace_links_for_lead(
            "L-1", [], linked_by_operator_id="ops@x.tr",
        )
    assert diff["added"] == []
    assert diff["removed"] == ["A-1", "A-2"]
    assert diff["kept"] == []
    assert diff["current"] == []


def test_replace_diff_mixed(fake_supabase):
    """Add + remove + keep all in one call."""
    sb, chain = fake_supabase
    _diff_setup(
        [
            {"id": "LK-1", "asset_id": "A-1"},
            {"id": "LK-2", "asset_id": "A-2"},
        ],
        (sb, chain),
    )
    with patch("app.db.supabase", sb):
        diff = lead_uploads.replace_links_for_lead(
            "L-1", ["A-2", "A-3"],  # drop A-1, keep A-2, add A-3
            linked_by_operator_id="ops@x.tr",
        )
    assert diff["added"] == ["A-3"]
    assert diff["removed"] == ["A-1"]
    assert diff["kept"] == ["A-2"]
    assert diff["current"] == ["A-2", "A-3"]


def test_replace_dedups_input(fake_supabase):
    """Duplicate asset_ids in the input collapse before diff
    computation — caller mistake shouldn't cause a unique-index
    constraint error."""
    sb, chain = fake_supabase
    _diff_setup([], (sb, chain))
    with patch("app.db.supabase", sb):
        diff = lead_uploads.replace_links_for_lead(
            "L-1", ["A-1", "A-1", "A-1"],
            linked_by_operator_id="admin",
        )
    assert diff["added"] == ["A-1"]
    assert diff["current"] == ["A-1"]


def test_replace_drops_empty_asset_ids(fake_supabase):
    """Empty strings filtered out — they'd violate the FK if
    inserted."""
    sb, chain = fake_supabase
    _diff_setup([], (sb, chain))
    with patch("app.db.supabase", sb):
        diff = lead_uploads.replace_links_for_lead(
            "L-1", ["", "A-1", ""],
            linked_by_operator_id="admin",
        )
    assert diff["added"] == ["A-1"]
    assert "" not in diff["current"]


def test_replace_idempotent_when_set_unchanged(fake_supabase):
    sb, chain = fake_supabase
    _diff_setup(
        [
            {"id": "LK-1", "asset_id": "A-1"},
            {"id": "LK-2", "asset_id": "A-2"},
        ],
        (sb, chain),
    )
    with patch("app.db.supabase", sb):
        diff = lead_uploads.replace_links_for_lead(
            "L-1", ["A-1", "A-2"],
            linked_by_operator_id="admin",
        )
    assert diff["added"] == []
    assert diff["removed"] == []
    assert sorted(diff["kept"]) == ["A-1", "A-2"]
    # No update / insert call on idempotent path.
    chain.update.assert_not_called()
    chain.insert.assert_not_called()


# ─── list_leads_for_asset ────────────────────────────────────────────


def test_list_leads_for_asset_returns_lead_ids(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(
        data=[{"lead_id": "L-1"}, {"lead_id": "L-2"}]
    )
    with patch("app.db.supabase", sb):
        out = lead_uploads.list_leads_for_asset("A-1")
    assert out == ["L-1", "L-2"]


def test_list_leads_for_asset_filters_tombstoned(fake_supabase):
    sb, chain = fake_supabase
    chain.execute.return_value = MagicMock(data=[])
    with patch("app.db.supabase", sb):
        lead_uploads.list_leads_for_asset("A-1")
    chain.is_.assert_called_with("deleted_at", "null")
