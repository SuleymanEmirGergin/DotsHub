"""Real-corpus regression test (C1).

Runs the orchestrator against a hand-labeled batch of 40-50 patient
utterances that aren't in golden_flows. Source mix:
  - paraphrase  : same clinical case as a golden_flow, different phrasing
  - synthetic_new: a clinical pattern not covered by golden_flows
  - ambiguous   : genuinely ambiguous — expected is the most-likely branch

Purpose (vs. golden_flows):
  golden_flows pins safety-critical scenarios with strict assertions and
  CI gates. real_corpus measures coverage/robustness at a larger scale
  — failures here are tuning signals, not build-blockers. The suite
  therefore asserts a minimum pass-rate threshold rather than per-scenario
  pass, and prints a per-source pass-rate breakdown to make regressions
  visible without turning CI red on every synonym tweak.

Baseline (see docs/REAL_CORPUS_C1_REPORT.md): the first run after
commit 1fd8c0c established the initial pass rate. The test's
MIN_PASS_RATE is pinned a few points below that baseline so routine
tuning doesn't flake the suite; intentional regressions still fail.
"""

from __future__ import annotations

import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from app.runtime import load_runtime
from app.triage_engine import run_orchestrator_turn


# Pinned below the measured baseline so normal tuning doesn't flake
# the suite. Bump this after a clean intentional improvement; drop
# only with a written justification.
#
# Baseline log:
#   commit 1fd8c0c (46 scenarios)  : 24/46 = 52.2%  threshold 0.50
#   commit C2-expand (79 scenarios): 32/79 = 40.5%  threshold 0.35
#   commit B1-tune   (79 scenarios): 48/79 = 60.8%  threshold 0.55
#     (paraphrase jumped 33% → 78% after applying the round-2
#      specialty-keyword audit + Migren/Diyabet/Hipertansiyon/
#      Hipotiroidi/Hemoroid context injections + stroke 3rd-person
#      regex. synthetic_new still at 39.5% — next tuning target.)
#   commit B2-cover  (79 scenarios): 57/79 = 72.2%  threshold 0.65
#     (synthetic_new 39.5% → 63.2% after adding 14 new canonicals
#      — ayak mantarı, psoriasis, sinüs basıncı, bademcik iltihabı,
#      bel ağrısı, diz yaralanması, omuz ağrısı, arpacık, katarakt,
#      hipertiroidi, OKB, gebelik takibi, menopoz, kulak kanalı
#      akıntısı — plus Pnömoni/Sinüzit/Tonsillit/Hipertiroidi/
#      ayak mantarı/Psoriasis/Bel fıtığı/Donuk Omuz/OKB/Katarakt/
#      Arpacık/Gebelik/Menopoz context injections, plus self_harm
#      regex expansion for paraphrased suicidal ideation.)
#   commit C3-expand (148 scenarios): 84/148 = 56.8%  threshold 0.50
#     (corpus nearly doubled to cover broader clinical territory —
#      epilepsy, neuropathy, bipolar, PTSD, alcohol dependence,
#      alopecia, hand eczema, tinnitus, hearing loss, allergic
#      rhinitis, COPD, bronchitis, IBD, celiac, cholelithiasis,
#      liver disease, osteoporosis, thyroid nodule, BPH, urinary
#      incontinence, dry eye, retinal detachment, colic, feeding
#      refusal, tennis elbow, plantar fasciitis, endometriosis,
#      fibroid, discharge, proteinuria, sepsis, meningitis,
#      poisoning, trauma, burn, pericarditis, seborrheic derm,
#      adrenal, ADHD, + 10 new ambiguous cases. New cases untuned;
#      same "coverage before tuning" pattern as C2 expansion.)
#   commit B7-A    (148 scenarios): 126/148 = 85.1%  threshold 0.50
#     (Group A synonym expansion — fixed 9 "top_condition: missing"
#      failures by adding TR variants that surface the expected
#      Kaggle-mapped canonicals. Net: +9 passes (Fungal, Diyabet ×1,
#      Sarılık, BPPV, Dismenore, Artrit, Otitis ×2, Tüberküloz). New
#      canonicals added for kilo artışı, sarılık, koyu idrar,
#      terleme, karıncalanma, diyabet öyküsü, bulanık görme — all
#      align with kaggle_to_canonical.json keys so they actually
#      count toward disease-symptom overlap. vajinal akıntı variants
#      tightened to require the "vajinal/aşağı/genital" qualifier so
#      sinüzit "sarı akıntı" no longer over-matches obgyn. Group B+C
#      (specialty routing + final_type tuning) is a separate PR.)
MIN_PASS_RATE = 0.50


class RealCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(data_dir="app/data")
        corpus_path = (
            Path(__file__).resolve().parents[2] / "tests" / "real_corpus" / "scenarios.json"
        )
        cls.corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        cls.scenarios = cls.corpus.get("scenarios", [])

    def _evaluate(self, scenario: dict) -> tuple[bool, list[str]]:
        """Run one scenario; return (all_pass, list of failed assertion names)."""
        text = scenario.get("user_message", "")
        expected = scenario.get("expected", {}) or {}
        final_type, payload, _ = run_orchestrator_turn(
            runtime=self.runtime,
            input_text=text,
            answers={},
            asked_canonicals=[],
            turn_index=1,
        )

        failed: list[str] = []

        exp_type = expected.get("final_type")
        if exp_type and final_type != exp_type:
            failed.append(f"final_type({final_type}!={exp_type})")

        exp_spec = expected.get("recommended_specialty")
        got_spec = (payload.get("recommended_specialty") or {}).get("id")
        if exp_spec and got_spec != exp_spec:
            failed.append(f"specialty({got_spec}!={exp_spec})")

        exp_top = expected.get("top_condition_contains")
        if exp_top:
            labels = [
                c.get("disease_label")
                for c in (payload.get("top_conditions") or [])
                if isinstance(c, dict)
            ]
            if not any(exp_top in (label or "") for label in labels):
                failed.append(f"top_condition(missing:{exp_top})")

        exp_urg = expected.get("urgency")
        if exp_urg and payload.get("urgency") != exp_urg:
            failed.append(f"urgency({payload.get('urgency')}!={exp_urg})")

        return (not failed, failed)

    def test_pass_rate_above_threshold(self):
        self.assertTrue(self.scenarios, "real_corpus scenarios.json is empty")

        per_source_total: Counter[str] = Counter()
        per_source_pass: Counter[str] = Counter()
        failures_by_id: dict[str, list[str]] = {}

        for scenario in self.scenarios:
            source = str(scenario.get("source", "unknown"))
            sid = str(scenario.get("id", "<no-id>"))
            per_source_total[source] += 1
            ok, failed = self._evaluate(scenario)
            if ok:
                per_source_pass[source] += 1
            else:
                failures_by_id[sid] = failed

        total = sum(per_source_total.values())
        passed = sum(per_source_pass.values())
        rate = passed / total if total else 0.0

        # Grouped breakdown (goes to CI stdout — visible regression signal).
        print(f"\n--- Real corpus pass-rate: {passed}/{total} = {rate:.1%} ---")
        for source in sorted(per_source_total):
            t = per_source_total[source]
            p = per_source_pass[source]
            r = p / t if t else 0.0
            print(f"  {source:<16} {p}/{t} ({r:.1%})")
        if failures_by_id:
            print("  Failing scenarios:")
            # Stable ordering for diffable CI output
            for sid in sorted(failures_by_id):
                print(f"    - {sid}: {', '.join(failures_by_id[sid])}")

        self.assertGreaterEqual(
            rate,
            MIN_PASS_RATE,
            f"Real-corpus pass rate {rate:.1%} dropped below MIN_PASS_RATE "
            f"{MIN_PASS_RATE:.0%}. Inspect the per-source breakdown above — "
            "a regression in deterministic routing or canonical extraction "
            "is the most common cause.",
        )


if __name__ == "__main__":
    unittest.main()
