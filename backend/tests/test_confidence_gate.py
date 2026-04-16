"""A9 confidence gate + label override tests — Stream A Session A9.

Tests the pure-function module ``backend/app/top_conditions_filter.py``.

These tests do not exercise the orchestrator integration (deferred per
``docs/medical/a9_integration.md``). Once the orchestrator is wired to
``filter_top_conditions``, an integration test should be added to
``test_triage_full_flow.py`` asserting the end-to-end envelope shape.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from app.top_conditions_filter import (
    MIN_CONFIDENCE_FOR_CONDITIONS,
    apply_top_conditions_gate,
    apply_label_overrides,
    clear_cache,
    filter_top_conditions,
    load_label_overrides,
)


# ── apply_top_conditions_gate ───────────────────────────────────────────────

@pytest.fixture
def sample_conditions():
    return [
        {"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.38},
        {"disease_label": "Migraine", "score_0_1": 0.22},
        {"disease_label": "Hypertension ", "score_0_1": 0.18},
    ]


def test_gate_suppresses_below_threshold(sample_conditions):
    """Confidence below 0.35 → empty list."""
    result = apply_top_conditions_gate(sample_conditions, confidence=0.30)
    assert result == []


def test_gate_allows_at_threshold(sample_conditions):
    """Confidence at exactly 0.35 → unchanged (>= is allowed)."""
    result = apply_top_conditions_gate(sample_conditions, confidence=0.35)
    assert result == sample_conditions


def test_gate_allows_above_threshold(sample_conditions):
    """High confidence → unchanged."""
    result = apply_top_conditions_gate(sample_conditions, confidence=0.80)
    assert result == sample_conditions


def test_gate_bypass_when_confidence_none(sample_conditions):
    """None confidence (legacy callers) → bypass gate."""
    result = apply_top_conditions_gate(sample_conditions, confidence=None)
    assert result == sample_conditions


def test_gate_handles_unparseable_confidence(sample_conditions, caplog):
    """Non-numeric confidence → bypass gate and log warning."""
    result = apply_top_conditions_gate(sample_conditions, confidence="bogus")  # type: ignore[arg-type]
    assert result == sample_conditions


def test_gate_accepts_custom_threshold(sample_conditions):
    """Caller can tighten the threshold."""
    # Confidence 0.50 is above default 0.35 but below custom 0.60
    result = apply_top_conditions_gate(sample_conditions, confidence=0.50, threshold=0.60)
    assert result == []


def test_gate_empty_list_passthrough():
    """Empty input stays empty."""
    assert apply_top_conditions_gate([], confidence=0.90) == []
    assert apply_top_conditions_gate([], confidence=0.10) == []


def test_gate_preserves_object_reference():
    """When conf is above threshold, the same list reference is returned."""
    conditions = [{"disease_label": "X", "score_0_1": 0.5}]
    result = apply_top_conditions_gate(conditions, confidence=0.90)
    assert result is conditions


def test_min_confidence_constant_value():
    """Document the threshold value — any change should be intentional."""
    assert MIN_CONFIDENCE_FOR_CONDITIONS == 0.35


# ── apply_label_overrides ───────────────────────────────────────────────────

def test_override_rewrites_label():
    """Override map rewrites disease_label and preserves source."""
    conditions = [
        {"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.7},
    ]
    overrides = {"Paralysis (brain hemorrhage)": "İnme / SVH şüphesi"}
    result = apply_label_overrides(conditions, overrides)
    assert result[0]["disease_label"] == "İnme / SVH şüphesi"
    assert result[0]["_source_label"] == "Paralysis (brain hemorrhage)"
    assert result[0]["score_0_1"] == 0.7


def test_override_leaves_unmapped_untouched():
    """Label not in override map → no change, no _source_label."""
    conditions = [{"disease_label": "Acne", "score_0_1": 0.5}]
    result = apply_label_overrides(conditions, {"Migraine": "Migren"})
    assert result[0]["disease_label"] == "Acne"
    assert "_source_label" not in result[0]


def test_override_does_not_mutate_input():
    """Input list/dicts remain untouched."""
    conditions = [{"disease_label": "Heart attack", "score_0_1": 0.9}]
    overrides = {"Heart attack": "Akut koroner sendrom şüphesi"}
    original_first = dict(conditions[0])
    result = apply_label_overrides(conditions, overrides)
    assert conditions[0] == original_first
    assert result is not conditions


def test_override_empty_map_passthrough():
    conditions = [{"disease_label": "X", "score_0_1": 0.1}]
    assert apply_label_overrides(conditions, {}) == conditions


def test_override_handles_trailing_space_label():
    """'Hypertension ' (trailing space bug in disease_to_specialty.json) → 'Hipertansiyon'."""
    conditions = [{"disease_label": "Hypertension ", "score_0_1": 0.8}]
    overrides = {"Hypertension ": "Hipertansiyon"}
    result = apply_label_overrides(conditions, overrides)
    assert result[0]["disease_label"] == "Hipertansiyon"


# ── load_label_overrides ────────────────────────────────────────────────────

def test_load_overrides_returns_dict():
    """Shipped JSON file loads as a non-empty dict."""
    clear_cache()
    overrides = load_label_overrides(force_reload=True)
    assert isinstance(overrides, dict)
    # Spot-check canonical override from A1 audit
    assert overrides.get("Paralysis (brain hemorrhage)") == "İnme / SVH şüphesi"


def test_load_overrides_cached():
    """Second call returns cached dict."""
    clear_cache()
    first = load_label_overrides()
    second = load_label_overrides()
    assert first is second


def test_load_overrides_missing_file(tmp_path):
    """Missing file → empty dict, no exception."""
    missing = tmp_path / "nope.json"
    overrides = load_label_overrides(path=missing)
    assert overrides == {}


def test_load_overrides_malformed_json(tmp_path):
    """Malformed JSON → empty dict, logged warning."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    overrides = load_label_overrides(path=bad)
    assert overrides == {}


def test_load_overrides_wrong_shape(tmp_path):
    """'overrides' not a dict → empty dict."""
    bad = tmp_path / "shape.json"
    bad.write_text(json.dumps({"overrides": ["not", "a", "dict"]}))
    overrides = load_label_overrides(path=bad)
    assert overrides == {}


# ── filter_top_conditions (full pipeline) ──────────────────────────────────

def test_filter_suppresses_and_leaves_empty():
    """Low confidence → empty regardless of overrides."""
    conditions = [{"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.3}]
    result = filter_top_conditions(conditions, confidence=0.20)
    assert result == []


def test_filter_applies_overrides_when_gate_passes():
    """High confidence → overrides applied."""
    conditions = [{"disease_label": "Heart attack", "score_0_1": 0.9}]
    overrides = {"Heart attack": "Akut koroner sendrom şüphesi"}
    result = filter_top_conditions(conditions, confidence=0.8, overrides=overrides)
    assert result[0]["disease_label"] == "Akut koroner sendrom şüphesi"


def test_filter_emergency_bypasses_gate():
    """EMERGENCY envelope → gate skipped, overrides still applied."""
    conditions = [{"disease_label": "Heart attack", "score_0_1": 0.9}]
    overrides = {"Heart attack": "Akut koroner sendrom şüphesi"}
    # Even with confidence well below threshold, emergency surfaces
    result = filter_top_conditions(
        conditions, confidence=0.10, envelope_type="EMERGENCY", overrides=overrides,
    )
    assert len(result) == 1
    assert result[0]["disease_label"] == "Akut koroner sendrom şüphesi"


def test_filter_loads_shipped_overrides_by_default():
    """When overrides=None, the shipped JSON is consulted."""
    clear_cache()
    conditions = [{"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.9}]
    result = filter_top_conditions(conditions, confidence=0.80)
    assert result[0]["disease_label"] == "İnme / SVH şüphesi"
    assert result[0]["_source_label"] == "Paralysis (brain hemorrhage)"
