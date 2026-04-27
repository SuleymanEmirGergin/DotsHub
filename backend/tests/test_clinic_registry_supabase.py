"""Hybrid clinic_registry — Supabase preferred, JSON fallback.

Behaviour pinned:
    * No SUPABASE_URL → JSON path. (Existing tests already cover this
      indirectly; we add an explicit unit test so the contract is loud.)
    * SUPABASE_URL set + table empty → JSON fallback (treat empty
      table as 'not yet seeded').
    * SUPABASE_URL set + table has rows → use Supabase; row metadata
      jsonb spread back to top-level for backward compat.
    * SUPABASE_URL set + Supabase raises → JSON fallback (failure-mode
      contract: a database outage must not take quotes offline).

Every test mocks the supabase client. No network in tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import clinic_registry


@pytest.fixture(autouse=True)
def _clear_caches(monkeypatch):
    # Ensure neither cache leaks between tests, and SUPABASE_URL doesn't
    # leak from the developer's env.
    clinic_registry.clear_cache()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    yield
    clinic_registry.clear_cache()


# ─── JSON path ───────────────────────────────────────────────────────


def test_unconfigured_supabase_uses_json():
    out = clinic_registry.all_clinics()
    assert len(out) >= 5
    # JSON file's first clinic id should appear.
    assert any(c["id"].startswith("clinic_") for c in out)


def test_get_clinic_unknown_returns_none():
    assert clinic_registry.get_clinic("nope") is None


def test_partially_configured_supabase_uses_json(monkeypatch):
    # Only SUPABASE_URL set — service key missing → not 'configured'.
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    out = clinic_registry.all_clinics()
    # Same shape as JSON path.
    assert len(out) >= 5


# ─── Supabase path ───────────────────────────────────────────────────


def _mock_supabase(rows):
    """Build a mock that mirrors the chained-call shape:
    sb.table(...).select(...).eq(...).execute().data."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = rows
    return sb


def test_supabase_configured_with_rows_uses_db(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    rows = [
        {
            "id": "clinic_db_1",
            "name": "DB Clinic 1",
            "city": "Istanbul",
            "country": "TR",
            "lat": 41.0,
            "lon": 29.0,
            "certifications": ["JCI"],
            "languages": ["tr", "en"],
            "procedures_offered": ["lasik"],
            "package_features": ["transfer"],
            "specialties_strength": ["ophthalmology"],
            "price_modifier": 1.0,
            "years_experience": 10,
            "before_after_count": 100,
            "average_rating_5": 4.5,
            "consult_response_hours": 6,
            "is_active": True,
            "metadata": {"extra_field": "spread_to_top_level"},
            "created_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-01T00:00:00Z",
        },
    ]
    mock_sb = _mock_supabase(rows)
    with patch("app.supabase_client.get_supabase", return_value=mock_sb):
        out = clinic_registry.all_clinics()
    assert len(out) == 1
    assert out[0]["id"] == "clinic_db_1"
    # metadata jsonb gets spread to top level.
    assert out[0]["extra_field"] == "spread_to_top_level"
    # internal columns stripped.
    assert "created_at" not in out[0]
    assert "is_active" not in out[0]


def test_supabase_empty_table_falls_back_to_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    mock_sb = _mock_supabase([])
    with patch("app.supabase_client.get_supabase", return_value=mock_sb):
        out = clinic_registry.all_clinics()
    # Empty DB → JSON has 8 sample clinics seeded into source.
    assert len(out) >= 5


def test_supabase_raises_falls_back_to_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    with patch(
        "app.supabase_client.get_supabase",
        side_effect=RuntimeError("postgrest down"),
    ):
        out = clinic_registry.all_clinics()
    assert len(out) >= 5  # JSON fallback activated


def test_supabase_cache_avoids_second_query(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    rows = [{
        "id": "c1", "name": "x", "city": "İstanbul", "country": "TR",
        "lat": 0, "lon": 0,
        "certifications": [], "languages": [], "procedures_offered": [],
        "package_features": [], "specialties_strength": [],
        "price_modifier": 1.0, "years_experience": 1,
        "before_after_count": 1, "average_rating_5": 4.0,
        "consult_response_hours": 1, "is_active": True, "metadata": {},
    }]
    mock_sb = _mock_supabase(rows)
    with patch("app.supabase_client.get_supabase", return_value=mock_sb) as p:
        clinic_registry.all_clinics()
        clinic_registry.all_clinics()
        clinic_registry.all_clinics()
    # Three calls but only one Supabase get — cache served the rest.
    assert p.call_count == 1


def test_clinics_for_procedure_filters_supabase_rows(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    rows = [
        {
            "id": "c_hair", "name": "Hair", "city": "İstanbul", "country": "TR",
            "lat": 0, "lon": 0,
            "certifications": [], "languages": ["tr"],
            "procedures_offered": ["fue_hair_transplant"],
            "package_features": [], "specialties_strength": [],
            "price_modifier": 1.0, "years_experience": 5,
            "before_after_count": 100, "average_rating_5": 4.0,
            "consult_response_hours": 4, "is_active": True, "metadata": {},
        },
        {
            "id": "c_eye", "name": "Eye", "city": "İzmir", "country": "TR",
            "lat": 0, "lon": 0,
            "certifications": [], "languages": ["tr"],
            "procedures_offered": ["lasik"],
            "package_features": [], "specialties_strength": [],
            "price_modifier": 1.0, "years_experience": 5,
            "before_after_count": 100, "average_rating_5": 4.0,
            "consult_response_hours": 4, "is_active": True, "metadata": {},
        },
    ]
    mock_sb = _mock_supabase(rows)
    with patch("app.supabase_client.get_supabase", return_value=mock_sb):
        out = clinic_registry.clinics_for_procedure("lasik")
    assert len(out) == 1
    assert out[0]["id"] == "c_eye"


def test_clear_cache_drops_both_layers(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    mock_sb = _mock_supabase([])
    with patch("app.supabase_client.get_supabase", return_value=mock_sb):
        clinic_registry.all_clinics()  # fills JSON cache (empty supabase)
    clinic_registry.clear_cache()
    # After clear, both should be re-queried — neither cache is set.
    assert clinic_registry._JSON_CACHE is None
    assert clinic_registry._SUPABASE_CACHE is None
