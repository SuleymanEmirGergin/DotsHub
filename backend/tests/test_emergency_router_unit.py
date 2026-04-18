"""Unit tests for emergency_router.py — rule-evaluation coverage.

The golden-flow and real-corpus suites exercise this module end-to-end
through run_orchestrator_turn, but they don't cover the boundary cases:
empty phrase lists, severity gating, require_any_group gate, tie-break
on rule_id, load_emergency_rules file reading. This file plugs those
gaps (coverage audit flagged lines 31, 43, 49, 55, 68, 87-88, 118,
130-131 as untouched).

Everything is pure — no mocks, no I/O (except load_emergency_rules test,
which uses tempfile).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.emergency_router import (
    EmergencyMatch,
    canon_any,
    contains_all,
    contains_any,
    evaluate_emergency,
    group_match,
    load_emergency_rules,
    norm_list,
    norm_text_tr,
)


class NormHelpersTests(unittest.TestCase):
    def test_norm_text_tr_lowercases(self):
        # emergency_router uses Python's str.lower() + regex punctuation
        # strip, not tr_lower; Turkish İ → "i̇" (i + combining dot) and
        # the combining dot is classified as punctuation, so it ends up
        # as "i stanbul". The important thing is that matching is stable.
        self.assertEqual(norm_text_tr("İSTANBUL"), "i stanbul")

    def test_norm_text_tr_empty_passthrough(self):
        self.assertEqual(norm_text_tr(""), "")

    def test_norm_list_dedupes_via_set(self):
        out = norm_list(["ateş", "ATEŞ", "ateş"])
        self.assertEqual(out, {"ateş"})

    def test_norm_list_drops_empty(self):
        self.assertEqual(norm_list([""]), set())

    def test_norm_list_none_safe(self):
        self.assertEqual(norm_list(None), set())  # type: ignore[arg-type]


class ContainsAnyTests(unittest.TestCase):
    def test_empty_phrases_returns_false(self):
        """Line 31 coverage: early return when phrase list is empty."""
        self.assertFalse(contains_any("ateşim var", []))

    def test_match_returns_true(self):
        self.assertTrue(contains_any("çok ateşim var", ["ateşim var"]))

    def test_no_match_returns_false(self):
        self.assertFalse(contains_any("ben iyiyim", ["ateşim var"]))

    def test_skips_empty_normalized_phrase(self):
        # Phrase normalizes to "" → skipped, remaining "ateş" hits
        self.assertTrue(contains_any("ateşim var", ["", "ateş"]))


class ContainsAllTests(unittest.TestCase):
    def test_empty_phrases_returns_false(self):
        """Line 43 coverage: empty list cannot satisfy 'all'."""
        self.assertFalse(contains_all("ateşim var", []))

    def test_all_phrases_present_returns_true(self):
        """Line 49 coverage: loop exhausts without a mismatch."""
        self.assertTrue(
            contains_all("şiddetli baş ağrısı ve ateş", ["baş ağrısı", "ateş"])
        )

    def test_missing_one_phrase_returns_false(self):
        self.assertFalse(
            contains_all("şiddetli baş ağrısı", ["baş ağrısı", "ateş"])
        )


class CanonAnyTests(unittest.TestCase):
    def test_empty_wanted_returns_false(self):
        """Line 55 coverage: empty wanted list cannot intersect."""
        self.assertFalse(canon_any({"ateş"}, []))

    def test_intersection_returns_true(self):
        self.assertTrue(canon_any({"ateş", "baş ağrısı"}, ["ateş"]))

    def test_no_intersection_returns_false(self):
        self.assertFalse(canon_any({"ateş"}, ["çarpıntı"]))


class GroupMatchTests(unittest.TestCase):
    def test_keyword_all_hit(self):
        """Line 68 coverage: keyword_all group branch."""
        self.assertTrue(
            group_match(
                "şiddetli baş ağrısı ve ateş",
                {"ateş", "baş ağrısı"},
                {"keyword_all": ["baş ağrısı", "ateş"]},
            )
        )

    def test_keyword_any_hit(self):
        self.assertTrue(
            group_match("ateşim var", set(), {"keyword_any": ["ateşim var"]})
        )

    def test_canonical_any_hit(self):
        self.assertTrue(
            group_match("whatever", {"ateş"}, {"canonical_any": ["ateş"]})
        )

    def test_no_match_returns_false(self):
        self.assertFalse(
            group_match("ben iyiyim", set(), {"keyword_any": ["ateş"]})
        )

    def test_empty_group_returns_false(self):
        self.assertFalse(group_match("", set(), {}))


class LoadEmergencyRulesTests(unittest.TestCase):
    def test_loads_valid_json_file(self):
        """Lines 87-88 coverage: file I/O path."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps({"rules": [{"id": "X", "severity": 3}]}),
                encoding="utf-8",
            )
            out = load_emergency_rules(str(path))
            self.assertEqual(out["rules"][0]["id"], "X")


class EvaluateEmergencyTests(unittest.TestCase):
    _STROKE_RULE = {
        "id": "stroke_redflags",
        "severity": 4,
        "keyword_any": ["yüz düşük", "konuşamıyorum"],
        "title_tr": "İnme şüphesi",
        "recommendation_tr": "112",
    }

    def test_no_rules_returns_none(self):
        result = evaluate_emergency(
            user_text="ateşim var",
            canonicals_tr=[],
            rules_cfg={"rules": []},
        )
        self.assertIsNone(result)

    def test_keyword_any_match_fires(self):
        result = evaluate_emergency(
            user_text="yüz düşük ve konuşamıyorum",
            canonicals_tr=[],
            rules_cfg={"rules": [self._STROKE_RULE]},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.rule_id, "stroke_redflags")
        self.assertEqual(result.severity, 4)

    def test_severity_below_threshold_skipped(self):
        """Line 118 coverage: rule below min_severity_to_trigger is skipped."""
        low_sev_rule = {**self._STROKE_RULE, "severity": 1}
        result = evaluate_emergency(
            user_text="yüz düşük",
            canonicals_tr=[],
            rules_cfg={
                "global": {"min_severity_to_trigger": 3},
                "rules": [low_sev_rule],
            },
        )
        self.assertIsNone(result)

    def test_keyword_all_hit_path(self):
        """Lines 130-131 coverage: keyword_all base-check branch."""
        rule = {
            "id": "combo",
            "severity": 3,
            "keyword_all": ["baş ağrısı", "ateş"],
            "title_tr": "x",
        }
        result = evaluate_emergency(
            user_text="şiddetli baş ağrısı ve yüksek ateş",
            canonicals_tr=[],
            rules_cfg={"rules": [rule]},
        )
        self.assertIsNotNone(result)
        self.assertIn("keyword_all", result.matched_on["reasons"])

    def test_require_any_group_blocks_bare_match(self):
        rule = {
            "id": "needs_group",
            "severity": 4,
            "keyword_any": ["göğüs ağrısı"],
            "require_any_group": [{"keyword_any": ["nefes darlığı"]}],
            "title_tr": "x",
        }
        # base hit but group requirement not met → suppressed
        result = evaluate_emergency(
            user_text="göğüs ağrısı var ama nefesim rahat",
            canonicals_tr=[],
            rules_cfg={"rules": [rule]},
        )
        self.assertIsNone(result)

    def test_require_any_group_passes_when_group_matches(self):
        rule = {
            "id": "needs_group",
            "severity": 4,
            "keyword_any": ["göğüs ağrısı"],
            "require_any_group": [{"keyword_any": ["nefes darlığı"]}],
            "title_tr": "x",
        }
        result = evaluate_emergency(
            user_text="göğüs ağrısı ve nefes darlığı",
            canonicals_tr=[],
            rules_cfg={"rules": [rule]},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.rule_id, "needs_group")
        self.assertIn("require_any_group", result.matched_on["reasons"])

    def test_severity_wins_tie_break(self):
        """Between two matching rules with different severity, higher wins."""
        high = {"id": "B_high", "severity": 5, "keyword_any": ["ateş"], "title_tr": "x"}
        low = {"id": "A_low", "severity": 2, "keyword_any": ["ateş"], "title_tr": "x"}
        result = evaluate_emergency(
            user_text="ateşim var",
            canonicals_tr=[],
            rules_cfg={"rules": [low, high]},
        )
        self.assertEqual(result.rule_id, "B_high")

    def test_rule_id_tie_break_deterministic(self):
        """Same severity → lexicographically smaller rule_id wins (stable)."""
        r1 = {"id": "aaa", "severity": 3, "keyword_any": ["ateş"], "title_tr": "x"}
        r2 = {"id": "zzz", "severity": 3, "keyword_any": ["ateş"], "title_tr": "x"}
        result = evaluate_emergency(
            user_text="ateşim var",
            canonicals_tr=[],
            rules_cfg={"rules": [r2, r1]},
        )
        self.assertEqual(result.rule_id, "aaa")

    def test_emergency_match_dataclass_shape(self):
        """EmergencyMatch carries all expected fields."""
        result = evaluate_emergency(
            user_text="yüz düşük",
            canonicals_tr=[],
            rules_cfg={"rules": [self._STROKE_RULE]},
        )
        self.assertIsInstance(result, EmergencyMatch)
        self.assertTrue(result.rule_id)
        self.assertTrue(result.title_tr)
        self.assertIn("user_text_norm", result.matched_on)
        self.assertIn("reasons", result.matched_on)

    def test_canonical_any_match_fires(self):
        rule = {
            "id": "canonical_match",
            "severity": 3,
            "canonical_any": ["ateş"],
            "title_tr": "x",
        }
        result = evaluate_emergency(
            user_text="",
            canonicals_tr=["ateş"],
            rules_cfg={"rules": [rule]},
        )
        self.assertIsNotNone(result)
        self.assertIn("canonical_any", result.matched_on["reasons"])


if __name__ == "__main__":
    unittest.main()
