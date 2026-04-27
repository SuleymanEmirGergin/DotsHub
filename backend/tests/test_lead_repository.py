"""Tests for the lead persistence layer.

Three concerns:
    1. Pure functions (`insert`, `record_outcome`, `soft_delete`,
       `get`) succeed when Supabase is configured + reachable.
    2. Each function fails-soft when Supabase is unconfigured or
       raises — returns the documented sentinel (False / None) so the
       caller can decide whether to keep going.
    3. KVKK consent gate: insert() never persists contact PII when
       consent_to_share is False.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import lead_repository


def _mock_sb():
    """Build a mock matching Supabase's chained-call surface."""
    sb = MagicMock()
    table = sb.table.return_value
    table.insert.return_value.execute.return_value.data = []
    table.update.return_value.eq.return_value.execute.return_value.data = []
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    return sb


# ─── insert ──────────────────────────────────────────────────────────


def test_insert_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    out = lead_repository.insert(
        lead_id="L1", session_id="S1", quote_id=None,
        procedure_id="lasik", clinic_id="clinic_x",
        consent_to_share=True, contact={"name": "x"}, notes="",
        locale="tr-TR", quoted_price_eur=1500,
    )
    assert out is False


def test_insert_writes_row_with_consent(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()
    with patch("app.supabase_client.get_supabase", return_value=sb):
        out = lead_repository.insert(
            lead_id="L1", session_id="S1", quote_id="Q1",
            procedure_id="lasik", clinic_id="clinic_x",
            consent_to_share=True,
            contact={"name": "Ali", "email": "a@b.co"},
            notes="hello", locale="tr-TR", quoted_price_eur=1500,
        )
    assert out is True
    inserted_row = sb.table.return_value.insert.call_args[0][0]
    assert inserted_row["id"] == "L1"
    assert inserted_row["quote_id"] == "Q1"
    assert inserted_row["consent_to_share"] is True
    # Contact is preserved when consent is given.
    assert inserted_row["contact"] == {"name": "Ali", "email": "a@b.co"}
    assert inserted_row["webhook_status"] == "pending"


def test_insert_drops_contact_pii_without_consent(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()
    with patch("app.supabase_client.get_supabase", return_value=sb):
        lead_repository.insert(
            lead_id="L2", session_id="S2", quote_id=None,
            procedure_id="lasik", clinic_id="clinic_x",
            consent_to_share=False,
            contact={"name": "Ali", "email": "a@b.co"},
            notes="", locale="tr-TR", quoted_price_eur=1500,
        )
    inserted_row = sb.table.return_value.insert.call_args[0][0]
    # KVKK: even though caller passed contact, persistence layer
    # nulls it out when consent is False.
    assert inserted_row["contact"] is None
    assert inserted_row["consent_to_share"] is False


def test_insert_returns_false_on_supabase_exception(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    with patch(
        "app.supabase_client.get_supabase",
        side_effect=RuntimeError("postgrest down"),
    ):
        out = lead_repository.insert(
            lead_id="L3", session_id="S3", quote_id=None,
            procedure_id="lasik", clinic_id="clinic_x",
            consent_to_share=False, contact={}, notes="",
            locale="tr-TR", quoted_price_eur=None,
        )
    assert out is False


# ─── record_outcome ──────────────────────────────────────────────────


def test_record_outcome_rejects_invalid_string(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    out = lead_repository.record_outcome("L1", "not_a_real_state")
    assert out is False


def test_record_outcome_writes_delivered_at_on_delivered(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()
    with patch("app.supabase_client.get_supabase", return_value=sb):
        lead_repository.record_outcome("L1", "delivered")
    update = sb.table.return_value.update.call_args[0][0]
    assert update["webhook_status"] == "delivered"
    assert "webhook_delivered_at" in update
    assert "webhook_attempted_at" in update


def test_record_outcome_omits_delivered_at_on_failure(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()
    with patch("app.supabase_client.get_supabase", return_value=sb):
        lead_repository.record_outcome("L1", "failed_4xx")
    update = sb.table.return_value.update.call_args[0][0]
    assert update["webhook_status"] == "failed_4xx"
    assert "webhook_delivered_at" not in update


def test_record_outcome_truncates_response_snippet(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()
    long_body = "X" * 1000
    with patch("app.supabase_client.get_supabase", return_value=sb):
        lead_repository.record_outcome(
            "L1", "failed_4xx", response_snippet=long_body
        )
    update = sb.table.return_value.update.call_args[0][0]
    assert len(update["webhook_response_snippet"]) == 200


# ─── soft_delete ─────────────────────────────────────────────────────


def test_soft_delete_returns_true_when_row_exists(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "L1"}
    ]
    with patch("app.supabase_client.get_supabase", return_value=sb):
        out = lead_repository.soft_delete("L1")
    assert out is True
    update = sb.table.return_value.update.call_args[0][0]
    # KVKK: contact + notes nulled out, soft-delete flag set.
    assert update["is_deleted"] is True
    assert update["contact"] is None
    assert update["notes"] == ""
    assert "deleted_at" in update


def test_soft_delete_returns_false_when_no_row_matched(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()  # update returns data=[] → 0 rows matched
    with patch("app.supabase_client.get_supabase", return_value=sb):
        out = lead_repository.soft_delete("not_a_real_lead")
    assert out is False


# ─── get ─────────────────────────────────────────────────────────────


def test_get_returns_row_when_found(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "L1", "session_id": "S1", "is_deleted": False}
    ]
    with patch("app.supabase_client.get_supabase", return_value=sb):
        out = lead_repository.get("L1")
    assert out is not None
    assert out["id"] == "L1"


def test_get_returns_none_when_not_found(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    sb = _mock_sb()  # select returns data=[]
    with patch("app.supabase_client.get_supabase", return_value=sb):
        out = lead_repository.get("nope")
    assert out is None


def test_get_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    out = lead_repository.get("anything")
    assert out is None
