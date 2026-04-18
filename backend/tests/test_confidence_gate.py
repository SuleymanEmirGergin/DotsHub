"""A9 confidence gate + label override tests — Stream A Session A9.

Tests the pure-function module ``backend/app/top_conditions_filter.py``.

These tests do not exercise the orchestrator integration (deferred per
``docs/medical/a9_integration.md``). Once the orchestrator is wired to
``filter_top_conditions``, an integration test should be added to
``test_triage_full_flow.py`` asserting the end-to-end envelope shape.

History: the suite was originally pytest-style, but pytest isn't in
``backend/requirements.txt`` and ``run_backend_regression.py`` shells
out to ``python -m unittest discover``. Before the admin_v5 /
push lazy-import fixes, unittest never reached this file — discovery
choked on earlier ImportErrors. Once those cleared, the missing pytest
dep surfaced here. Converted to stdlib unittest so we stop relying on
a dev-tool dep we never declared; semantics preserved.
"""

from __future__ import annotations

import json
import unittest
import tempfile
from pathlib import Path

from app.top_conditions_filter import (
    MIN_CONFIDENCE_FOR_CONDITIONS,
    apply_top_conditions_gate,
    apply_label_overrides,
    clear_cache,
    filter_top_conditions,
    load_label_overrides,
)


def _sample_conditions():
    return [
        {"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.38},
        {"disease_label": "Migraine", "score_0_1": 0.22},
        {"disease_label": "Hypertension ", "score_0_1": 0.18},
    ]


class ApplyTopConditionsGateTests(unittest.TestCase):
    def test_gate_suppresses_below_threshold(self):
        """Confidence below 0.35 → empty list."""
        result = apply_top_conditions_gate(_sample_conditions(), confidence=0.30)
        self.assertEqual(result, [])

    def test_gate_allows_at_threshold(self):
        """Confidence at exactly 0.35 → unchanged (>= is allowed)."""
        conds = _sample_conditions()
        result = apply_top_conditions_gate(conds, confidence=0.35)
        self.assertEqual(result, conds)

    def test_gate_allows_above_threshold(self):
        """High confidence → unchanged."""
        conds = _sample_conditions()
        result = apply_top_conditions_gate(conds, confidence=0.80)
        self.assertEqual(result, conds)

    def test_gate_bypass_when_confidence_none(self):
        """None confidence (legacy callers) → bypass gate."""
        conds = _sample_conditions()
        result = apply_top_conditions_gate(conds, confidence=None)
        self.assertEqual(result, conds)

    def test_gate_handles_unparseable_confidence(self):
        """Non-numeric confidence → bypass gate and log warning."""
        conds = _sample_conditions()
        result = apply_top_conditions_gate(conds, confidence="bogus")  # type: ignore[arg-type]
        self.assertEqual(result, conds)

    def test_gate_accepts_custom_threshold(self):
        """Caller can tighten the threshold."""
        # Confidence 0.50 is above default 0.35 but below custom 0.60
        result = apply_top_conditions_gate(_sample_conditions(), confidence=0.50, threshold=0.60)
        self.assertEqual(result, [])

    def test_gate_empty_list_passthrough(self):
        """Empty input stays empty."""
        self.assertEqual(apply_top_conditions_gate([], confidence=0.90), [])
        self.assertEqual(apply_top_conditions_gate([], confidence=0.10), [])

    def test_gate_preserves_object_reference(self):
        """When conf is above threshold, the same list reference is returned."""
        conditions = [{"disease_label": "X", "score_0_1": 0.5}]
        result = apply_top_conditions_gate(conditions, confidence=0.90)
        self.assertIs(result, conditions)

    def test_min_confidence_constant_value(self):
        """Document the threshold value — any change should be intentional."""
        self.assertEqual(MIN_CONFIDENCE_FOR_CONDITIONS, 0.35)


class ApplyLabelOverridesTests(unittest.TestCase):
    def test_override_rewrites_label(self):
        """Override map rewrites disease_label and preserves source."""
        conditions = [
            {"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.7},
        ]
        overrides = {"Paralysis (brain hemorrhage)": "İnme / SVH şüphesi"}
        result = apply_label_overrides(conditions, overrides)
        self.assertEqual(result[0]["disease_label"], "İnme / SVH şüphesi")
        self.assertEqual(result[0]["_source_label"], "Paralysis (brain hemorrhage)")
        self.assertEqual(result[0]["score_0_1"], 0.7)

    def test_override_leaves_unmapped_untouched(self):
        """Label not in override map → no change, no _source_label."""
        conditions = [{"disease_label": "Acne", "score_0_1": 0.5}]
        result = apply_label_overrides(conditions, {"Migraine": "Migren"})
        self.assertEqual(result[0]["disease_label"], "Acne")
        self.assertNotIn("_source_label", result[0])

    def test_override_does_not_mutate_input(self):
        """Input list/dicts remain untouched."""
        conditions = [{"disease_label": "Heart attack", "score_0_1": 0.9}]
        overrides = {"Heart attack": "Akut koroner sendrom şüphesi"}
        original_first = dict(conditions[0])
        result = apply_label_overrides(conditions, overrides)
        self.assertEqual(conditions[0], original_first)
        self.assertIsNot(result, conditions)

    def test_override_empty_map_passthrough(self):
        conditions = [{"disease_label": "X", "score_0_1": 0.1}]
        self.assertEqual(apply_label_overrides(conditions, {}), conditions)

    def test_override_handles_trailing_space_label(self):
        """'Hypertension ' (trailing space bug in disease_to_specialty.json) → 'Hipertansiyon'."""
        conditions = [{"disease_label": "Hypertension ", "score_0_1": 0.8}]
        overrides = {"Hypertension ": "Hipertansiyon"}
        result = apply_label_overrides(conditions, overrides)
        self.assertEqual(result[0]["disease_label"], "Hipertansiyon")


class LoadLabelOverridesTests(unittest.TestCase):
    def test_load_overrides_returns_dict(self):
        """Shipped JSON file loads as a non-empty dict."""
        clear_cache()
        overrides = load_label_overrides(force_reload=True)
        self.assertIsInstance(overrides, dict)
        # Spot-check canonical override from A1 audit
        self.assertEqual(overrides.get("Paralysis (brain hemorrhage)"), "İnme / SVH şüphesi")

    def test_load_overrides_cached(self):
        """Second call returns cached dict."""
        clear_cache()
        first = load_label_overrides()
        second = load_label_overrides()
        self.assertIs(first, second)

    def test_load_overrides_missing_file(self):
        """Missing file → empty dict, no exception."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            overrides = load_label_overrides(path=missing)
            self.assertEqual(overrides, {})

    def test_load_overrides_malformed_json(self):
        """Malformed JSON → empty dict, logged warning."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json")
            overrides = load_label_overrides(path=bad)
            self.assertEqual(overrides, {})

    def test_load_overrides_wrong_shape(self):
        """'overrides' not a dict → empty dict."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "shape.json"
            bad.write_text(json.dumps({"overrides": ["not", "a", "dict"]}))
            overrides = load_label_overrides(path=bad)
            self.assertEqual(overrides, {})


class FilterTopConditionsTests(unittest.TestCase):
    def test_filter_suppresses_and_leaves_empty(self):
        """Low confidence → empty regardless of overrides."""
        conditions = [{"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.3}]
        result = filter_top_conditions(conditions, confidence=0.20)
        self.assertEqual(result, [])

    def test_filter_applies_overrides_when_gate_passes(self):
        """High confidence → overrides applied."""
        conditions = [{"disease_label": "Heart attack", "score_0_1": 0.9}]
        overrides = {"Heart attack": "Akut koroner sendrom şüphesi"}
        result = filter_top_conditions(conditions, confidence=0.8, overrides=overrides)
        self.assertEqual(result[0]["disease_label"], "Akut koroner sendrom şüphesi")

    def test_filter_emergency_bypasses_gate(self):
        """EMERGENCY envelope → gate skipped, overrides still applied."""
        conditions = [{"disease_label": "Heart attack", "score_0_1": 0.9}]
        overrides = {"Heart attack": "Akut koroner sendrom şüphesi"}
        # Even with confidence well below threshold, emergency surfaces
        result = filter_top_conditions(
            conditions, confidence=0.10, envelope_type="EMERGENCY", overrides=overrides,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["disease_label"], "Akut koroner sendrom şüphesi")

    def test_filter_loads_shipped_overrides_by_default(self):
        """When overrides=None, the shipped JSON is consulted."""
        clear_cache()
        conditions = [{"disease_label": "Paralysis (brain hemorrhage)", "score_0_1": 0.9}]
        result = filter_top_conditions(conditions, confidence=0.80)
        self.assertEqual(result[0]["disease_label"], "İnme / SVH şüphesi")
        self.assertEqual(result[0]["_source_label"], "Paralysis (brain hemorrhage)")


if __name__ == "__main__":
    unittest.main()
