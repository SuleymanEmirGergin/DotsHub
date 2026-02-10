from __future__ import annotations

import json
from pathlib import Path
import unittest

from app.runtime import load_runtime
from app.triage_engine import run_orchestrator_turn


class GoldenFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(data_dir="app/data")
        cls.scenarios_dir = Path(__file__).resolve().parents[2] / "tests" / "golden_flows"

    def _run_scenario(self, scenario: dict):
        input_text = ""
        answers = {}
        asked_canonicals = []

        final_type = "ERROR"
        final_payload = {}

        for turn_index, step in enumerate(scenario.get("input", []), start=1):
            user_message = str(step.get("user_message") or "").strip()
            if user_message:
                input_text = (input_text + "\n" + user_message).strip()

            answer = step.get("answer")
            if isinstance(answer, dict):
                canonical = str(answer.get("canonical") or "").strip()
                value = str(answer.get("value") or "").strip()
                if canonical:
                    answers[canonical] = value
                    if canonical not in asked_canonicals:
                        asked_canonicals.append(canonical)

            final_type, final_payload, _ = run_orchestrator_turn(
                runtime=self.runtime,
                input_text=input_text,
                answers=answers,
                asked_canonicals=asked_canonicals,
                turn_index=turn_index,
            )

            if final_type in {"EMERGENCY", "ERROR"}:
                break

        return final_type, final_payload

    def test_golden_flows(self):
        scenario_files = sorted(self.scenarios_dir.glob("*.json"))
        self.assertTrue(scenario_files, "No golden flow scenario files found.")

        for scenario_path in scenario_files:
            scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
            expected = scenario.get("expected", {})
            with self.subTest(scenario=scenario_path.name):
                final_type, payload = self._run_scenario(scenario)
                self.assertEqual(final_type, expected.get("final_type"))

                expected_specialty = expected.get("recommended_specialty")
                if expected_specialty:
                    self.assertEqual(
                        (payload.get("recommended_specialty") or {}).get("id"),
                        expected_specialty,
                    )

                expected_top = expected.get("top_condition_contains")
                if expected_top:
                    top_conditions = [
                        c.get("disease_label")
                        for c in (payload.get("top_conditions") or [])
                        if isinstance(c, dict)
                    ]
                    self.assertTrue(
                        any(expected_top in (label or "") for label in top_conditions),
                        f"Expected '{expected_top}' in top conditions: {top_conditions}",
                    )

                expected_urgency = expected.get("urgency")
                if expected_urgency:
                    self.assertEqual(payload.get("urgency"), expected_urgency)


if __name__ == "__main__":
    unittest.main()
