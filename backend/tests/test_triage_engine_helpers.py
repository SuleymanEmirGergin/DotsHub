"""Unit tests for pure helpers in triage_engine.py.

The orchestrator itself is covered end-to-end by golden_flows,
real_corpus, and test_triage_engine_regression. This file fills the
coverage gaps that those integration paths don't hit — small helper
functions with defensive fallbacks when settings fields are missing
or the tenant catalog is empty.

Why these are worth unit-testing separately:
  _inj_high / _inj_medium / _inj_low read settings but have to tolerate
  a test or shadow_eval that patched the settings object and left a
  field as None or a non-numeric string. The except clauses are the
  safety net for ops mistakes; if they ever disappear, the orchestrator
  becomes brittle to live config edits.

  _curated_injected_labels falls back to a hardcoded set when the tenant
  catalog is empty. That path fires whenever a new tenant is provisioned
  before its curated_conditions.json is written.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.triage_engine import (
    _CURATED_INJECTED_LABELS_FALLBACK,
    _curated_injected_labels,
    _result_top_gate,
    _inj_high,
    _inj_low,
    _inj_medium,
)


class InjectionScoreHelpersTests(unittest.TestCase):
    def test_inj_high_reads_from_settings(self):
        from app import triage_engine

        with patch.object(triage_engine.settings, "CURATED_INJECTION_SCORE_HIGH", 0.85):
            self.assertEqual(_inj_high(), 0.85)

    def test_inj_high_falls_back_on_missing_attr(self):
        """Line 42-43 analog: AttributeError when setting not defined."""
        # Simulate settings missing the attribute entirely by forcing
        # float() on a non-numeric value (the except covers all 3 cases:
        # AttributeError, TypeError, ValueError).
        from app import triage_engine

        with patch.object(triage_engine.settings, "CURATED_INJECTION_SCORE_HIGH", None):
            self.assertEqual(_inj_high(), 0.70)

    def test_inj_medium_reads_from_settings(self):
        from app import triage_engine

        with patch.object(triage_engine.settings, "CURATED_INJECTION_SCORE_MEDIUM", 0.65):
            self.assertEqual(_inj_medium(), 0.65)

    def test_inj_medium_falls_back_on_non_numeric(self):
        from app import triage_engine

        with patch.object(
            triage_engine.settings, "CURATED_INJECTION_SCORE_MEDIUM", "not-a-number"
        ):
            self.assertEqual(_inj_medium(), 0.60)

    def test_inj_low_reads_from_settings(self):
        from app import triage_engine

        with patch.object(triage_engine.settings, "CURATED_INJECTION_SCORE_LOW", 0.50):
            self.assertEqual(_inj_low(), 0.50)

    def test_inj_low_falls_back_on_none(self):
        from app import triage_engine

        with patch.object(triage_engine.settings, "CURATED_INJECTION_SCORE_LOW", None):
            self.assertEqual(_inj_low(), 0.55)


class GateThresholdTests(unittest.TestCase):
    def test_reads_from_settings(self):
        from app import triage_engine

        with patch.object(triage_engine.settings, "RESULT_TOP_CONDITIONS_GATE", 0.30):
            self.assertEqual(_result_top_gate(), 0.30)

    def test_falls_back_on_bad_value(self):
        from app import triage_engine

        with patch.object(triage_engine.settings, "RESULT_TOP_CONDITIONS_GATE", None):
            self.assertEqual(_result_top_gate(), 0.25)


class CuratedInjectedLabelsTests(unittest.TestCase):
    def test_empty_catalog_falls_back_to_hardcoded(self):
        """Line 101 coverage: empty curated_conditions → fallback set."""
        runtime = SimpleNamespace(curated_conditions={})
        out = _curated_injected_labels(runtime)  # type: ignore[arg-type]
        self.assertEqual(out, _CURATED_INJECTED_LABELS_FALLBACK)
        # Spot-check a well-known fallback label
        self.assertIn("Panik Bozukluk", out)

    def test_none_catalog_falls_back(self):
        runtime = SimpleNamespace(curated_conditions=None)
        out = _curated_injected_labels(runtime)  # type: ignore[arg-type]
        self.assertEqual(out, _CURATED_INJECTED_LABELS_FALLBACK)

    def test_populated_catalog_returns_catalog_keys(self):
        """Non-empty catalog wins over the fallback — the whole point
        of making the set tenant-aware."""
        runtime = SimpleNamespace(
            curated_conditions={
                "conditions": {
                    "Test Label A": {"tr": "Etiket A"},
                    "Test Label B": {"tr": "Etiket B"},
                }
            }
        )
        out = _curated_injected_labels(runtime)  # type: ignore[arg-type]
        self.assertEqual(set(out), {"Test Label A", "Test Label B"})

    def test_conditions_empty_but_present_falls_back(self):
        """conditions={} is still empty; fall back to hardcoded."""
        runtime = SimpleNamespace(curated_conditions={"conditions": {}})
        out = _curated_injected_labels(runtime)  # type: ignore[arg-type]
        self.assertEqual(out, _CURATED_INJECTED_LABELS_FALLBACK)


if __name__ == "__main__":
    unittest.main()
