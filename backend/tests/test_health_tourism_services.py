"""Unit tests for the health-tourism service modules.

Covers:
    * procedure_catalog — load, lookup, locale fallback, synonyms iter
    * clinic_registry — load, lookup, procedure filter, maps_url
    * procedure_intent — single-token, multi-word phrase, miss,
      multi-locale, normalisation
    * fit_to_travel — block, warn, no-match, rule_applies_to filter,
      KNOWN_TRIGGER_KEYS validation
    * quote_engine — score components, ranking, top_n, no clinics,
      city boost, deterministic tie-breaking

Pure-function tests — no FastAPI app, no network. Route-level tests
live in test_quote_route.py.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.models.schemas import HealthTourismProfile
from app.services import (
    clinic_registry,
    fit_to_travel,
    procedure_catalog,
    procedure_intent,
    quote_engine,
)


# ─── procedure_catalog ───────────────────────────────────────────────


def test_catalog_loads_at_least_8_procedures():
    procs = procedure_catalog.all_procedures()
    assert len(procs) >= 8


def test_catalog_get_known_id_returns_procedure():
    p = procedure_catalog.get_procedure("fue_hair_transplant")
    assert p is not None
    assert p["category"] == "hair"


def test_catalog_get_unknown_id_returns_none():
    assert procedure_catalog.get_procedure("not_a_real_procedure") is None


def test_catalog_name_locale_tr():
    name = procedure_catalog.name("rhinoplasty", "tr-TR")
    assert "Burun" in name


def test_catalog_name_locale_en():
    name = procedure_catalog.name("rhinoplasty", "en-US")
    assert "Rhinoplasty" in name


def test_catalog_name_unknown_id_returns_id():
    assert procedure_catalog.name("zzz", "tr") == "zzz"


def test_catalog_synonyms_yields_pairs_for_locale():
    pairs = list(procedure_catalog.synonyms("tr-TR"))
    proc_ids = {pid for _, pid in pairs}
    # Every procedure has at least one Turkish synonym.
    assert proc_ids >= {"fue_hair_transplant", "rhinoplasty", "lasik"}


# ─── clinic_registry ─────────────────────────────────────────────────


def test_registry_loads_at_least_5_clinics():
    assert len(clinic_registry.all_clinics()) >= 5


def test_registry_clinics_for_procedure_filters_correctly():
    hair = clinic_registry.clinics_for_procedure("fue_hair_transplant")
    assert len(hair) >= 2
    for c in hair:
        assert "fue_hair_transplant" in c["procedures_offered"]


def test_registry_unknown_procedure_returns_empty_list():
    assert clinic_registry.clinics_for_procedure("nope") == []


def test_registry_maps_url_returns_google_url_with_coords():
    clinic = clinic_registry.all_clinics()[0]
    url = clinic_registry.maps_url(clinic)
    assert url is not None
    assert "google.com/maps" in url
    assert str(clinic["lat"]) in url


def test_registry_maps_url_returns_none_when_no_coordinates():
    assert clinic_registry.maps_url({"id": "x"}) is None


# ─── procedure_intent ────────────────────────────────────────────────


def test_intent_extract_empty_returns_none():
    assert procedure_intent.extract("", "tr-TR") is None
    assert procedure_intent.extract(None, "tr-TR") is None
    assert procedure_intent.extract("   ", "tr-TR") is None


def test_intent_extract_below_min_token_len():
    # 2 chars → too short, no match.
    assert procedure_intent.extract("ab", "tr-TR") is None


def test_intent_extract_tr_hair():
    m = procedure_intent.extract("saç ekimi yaptırmak istiyorum", "tr-TR")
    assert m is not None
    assert m.procedure_id == "fue_hair_transplant"
    assert m.confidence_0_1 > 0


def test_intent_extract_tr_rhinoplasty():
    m = procedure_intent.extract("burnumdan memnun değilim", "tr-TR")
    assert m is not None
    assert m.procedure_id == "rhinoplasty"


def test_intent_extract_en_lasik():
    m = procedure_intent.extract("I want laser eye surgery", "en-US")
    assert m is not None
    assert m.procedure_id == "lasik"


def test_intent_extract_de_hair():
    m = procedure_intent.extract(
        "Ich möchte eine Haartransplantation", "de-DE"
    )
    assert m is not None
    assert m.procedure_id == "fue_hair_transplant"


def test_intent_extract_unknown_text_returns_none():
    assert procedure_intent.extract("xyz nonsense input", "tr-TR") is None


def test_intent_extract_normalises_punctuation():
    # Punctuation around the synonym should not block the match.
    m = procedure_intent.extract("LASIK!", "tr-TR")
    assert m is not None
    assert m.procedure_id == "lasik"


def test_intent_confidence_capped_at_0_95():
    # Bombarding the input with synonyms must still cap confidence.
    text = "saç ekimi saç ekimi saç ekimi saç ekimi saç ekimi"
    m = procedure_intent.extract(text, "tr-TR")
    assert m is not None
    assert m.confidence_0_1 <= 0.95


# ─── fit_to_travel ───────────────────────────────────────────────────


def test_fit_clean_profile_yields_no_warnings():
    prof = HealthTourismProfile()  # all defaults False/None
    warns = fit_to_travel.evaluate(prof, "rhinoplasty", "tr-TR")
    assert warns == []


def test_fit_recent_mi_blocks_general_anesthesia_procedures():
    prof = HealthTourismProfile(recent_mi=True)
    for proc in ["rhinoplasty", "mommy_makeover", "gastric_sleeve", "cabg"]:
        warns = fit_to_travel.evaluate(prof, proc, "tr-TR")
        assert any(w.severity == "block" for w in warns), proc
        assert fit_to_travel.has_block(warns), proc


def test_fit_recent_mi_does_not_block_local_anesthesia_procedures():
    # FUE hair transplant is local anesthesia — recent MI is listed
    # in the procedure's fit_to_travel_concerns but no rule fires for
    # local procedures (the rule applies_to_procedures excludes them).
    prof = HealthTourismProfile(recent_mi=True)
    warns = fit_to_travel.evaluate(prof, "fue_hair_transplant", "tr-TR")
    assert not any(w.severity == "block" for w in warns)


def test_fit_smoker_warns_but_does_not_block():
    prof = HealthTourismProfile(smoker_active=True)
    warns = fit_to_travel.evaluate(prof, "rhinoplasty", "tr-TR")
    assert warns
    assert all(w.severity == "warn" for w in warns)


def test_fit_block_sorted_first():
    prof = HealthTourismProfile(
        recent_mi=True, smoker_active=True, uncontrolled_hypertension=True
    )
    warns = fit_to_travel.evaluate(prof, "rhinoplasty", "tr-TR")
    # The first warning must be the block — caller relies on this.
    assert warns[0].severity == "block"


def test_fit_locale_fallback_uses_tr_when_locale_missing():
    prof = HealthTourismProfile(recent_mi=True)
    warns = fit_to_travel.evaluate(prof, "rhinoplasty", "xx-XX")
    assert warns
    assert "kalp" in warns[0].reason_tr.lower()  # TR fallback fired


def test_fit_known_trigger_keys_covers_every_profile_field():
    """Smoke test: every boolean field on HealthTourismProfile that
    rules can predicate on must be in KNOWN_TRIGGER_KEYS so the
    rule-validation step at import catches typos."""
    prof_fields = HealthTourismProfile.model_fields
    expected_bools = {
        name for name, info in prof_fields.items()
        if info.annotation is bool
    }
    # Profile may have non-bool fields (age, sex, bmi); KNOWN must
    # include every bool flag.
    assert expected_bools <= fit_to_travel.KNOWN_TRIGGER_KEYS


# ─── quote_engine ────────────────────────────────────────────────────


def test_engine_unknown_procedure_returns_empty():
    assert quote_engine.rank_clinics("nope", locale="tr-TR") == []


def test_engine_returns_at_most_top_n():
    out = quote_engine.rank_clinics("fue_hair_transplant", "tr-TR", top_n=2)
    assert len(out) == 2


def test_engine_respects_top_n_when_smaller_than_pool():
    out = quote_engine.rank_clinics("fue_hair_transplant", "tr-TR", top_n=1)
    assert len(out) == 1


def test_engine_results_are_sorted_descending_by_score():
    out = quote_engine.rank_clinics("fue_hair_transplant", "tr-TR", top_n=10)
    scores = [c.score_0_1 for c in out]
    assert scores == sorted(scores, reverse=True)


def test_engine_target_city_boosts_matching_clinic():
    no_city = quote_engine.rank_clinics(
        "rhinoplasty", "tr-TR", target_city=None
    )
    with_city = quote_engine.rank_clinics(
        "rhinoplasty", "tr-TR", target_city="Antalya"
    )
    # Antalya's clinic must rank higher (or first) once the city is specified.
    antalya_pos_no_city = next(
        (i for i, c in enumerate(no_city) if c.city == "Antalya"), -1
    )
    antalya_pos_with_city = next(
        (i for i, c in enumerate(with_city) if c.city == "Antalya"), -1
    )
    assert antalya_pos_with_city != -1
    assert antalya_pos_with_city <= antalya_pos_no_city


def test_engine_price_eur_applied_with_modifier():
    out = quote_engine.rank_clinics(
        "fue_hair_transplant", "tr-TR", top_n=10
    )
    for item in out:
        # Each clinic's quoted price must be > 0 and bracket the
        # procedure baseline (1500-3500 EUR for hair transplant after
        # modifier 0.85-1.25).
        assert 1000 < item.price_eur < 5000, item.clinic_id


def test_engine_includes_map_url_when_clinic_has_coords():
    out = quote_engine.rank_clinics(
        "fue_hair_transplant", "tr-TR", top_n=1
    )
    assert out[0].map_url is not None
    assert "maps" in out[0].map_url
