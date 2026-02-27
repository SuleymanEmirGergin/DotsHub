from __future__ import annotations

from types import SimpleNamespace
from time import perf_counter
import unittest

from app.runtime import load_runtime
from app.triage_engine import _generate_candidates, run_orchestrator_turn


class TriageEngineRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = load_runtime(data_dir="app/data")

    def test_uti_text_returns_result(self):
        envelope_type, payload, _ = run_orchestrator_turn(
            runtime=self.runtime,
            input_text="idrar yaparken yan\u0131yor, \u00e7ok s\u0131k idrara \u00e7\u0131k\u0131yorum",
            answers={},
            asked_canonicals=[],
            turn_index=1,
        )

        self.assertEqual(envelope_type, "RESULT")
        self.assertEqual(payload["recommended_specialty"]["id"], "urology_internal")
        top_conditions = payload.get("top_conditions") or []
        self.assertTrue(top_conditions)
        first = top_conditions[0]
        self.assertTrue(isinstance(first.get("disease_description"), str))
        self.assertTrue(bool(first.get("disease_description", "").strip()))

    def test_missing_description_map_does_not_break_result_path(self):
        original_descriptions = self.runtime.disease_descriptions_en
        try:
            self.runtime.disease_descriptions_en = {}
            envelope_type, payload, _ = run_orchestrator_turn(
                runtime=self.runtime,
                input_text="idrar yaparken yan\u0131yor, \u00e7ok s\u0131k idrara \u00e7\u0131k\u0131yorum",
                answers={},
                asked_canonicals=[],
                turn_index=1,
            )
        finally:
            self.runtime.disease_descriptions_en = original_descriptions

        self.assertEqual(envelope_type, "RESULT")
        top_conditions = payload.get("top_conditions") or []
        self.assertTrue(top_conditions)
        self.assertTrue(
            all(
                "disease_description" not in condition
                for condition in top_conditions
                if isinstance(condition, dict)
            )
        )

    def test_dizziness_nausea_no_crash_valid_envelope(self):
        envelope_type, payload, _ = run_orchestrator_turn(
            runtime=self.runtime,
            input_text="ba\u015f\u0131m d\u00f6n\u00fcyor, midem bulan\u0131yor",
            answers={},
            asked_canonicals=[],
            turn_index=1,
        )

        self.assertIn(envelope_type, {"QUESTION", "RESULT"})
        self.assertIsInstance(payload, dict)
        if envelope_type == "QUESTION":
            self.assertTrue(payload.get("question_tr"))
        if envelope_type == "RESULT":
            self.assertTrue(payload.get("recommended_specialty", {}).get("id"))

    def test_chest_emergency(self):
        envelope_type, payload, _ = run_orchestrator_turn(
            runtime=self.runtime,
            input_text="g\u00f6\u011fs\u00fcmde bask\u0131 var, nefesim dar",
            answers={},
            asked_canonicals=[],
            turn_index=1,
        )

        self.assertEqual(envelope_type, "EMERGENCY")
        self.assertEqual(payload.get("urgency"), "EMERGENCY")

    def test_null_map_does_not_crash_in_candidate_generation(self):
        fake_runtime = SimpleNamespace(
            disease_to_trcanonicals={"MockDisease": {"ba\u015f a\u011fr\u0131s\u0131"}},
            symptom_map_en_to_tr={
                "headache": "ba\u015f a\u011fr\u0131s\u0131",
                "family_history": None,
            },
            symptom_severity_en={"headache": 4},
            canonical_to_en_symptoms={"ba\u015f a\u011fr\u0131s\u0131": ["headache"]},
        )

        candidates = _generate_candidates(
            user_canonicals_tr=["ba\u015f a\u011fr\u0131s\u0131"],
            runtime=fake_runtime,
            top_n=3,
        )

        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["disease_label"], "MockDisease")

    def test_deterministic_same_input_same_output(self):
        kwargs = dict(
            runtime=self.runtime,
            input_text="idrar yanmas\u0131 ve s\u0131k idrara \u00e7\u0131kma var",
            answers={},
            asked_canonicals=[],
            turn_index=1,
        )
        first = run_orchestrator_turn(**kwargs)
        second = run_orchestrator_turn(**kwargs)
        self.assertEqual(first, second)

    def test_local_p95_response_time_smoke(self):
        samples = []
        for _ in range(30):
            start = perf_counter()
            run_orchestrator_turn(
                runtime=self.runtime,
                input_text="ba\u015f\u0131m a\u011fr\u0131yor ve midem bulan\u0131yor",
                answers={},
                asked_canonicals=[],
                turn_index=1,
            )
            samples.append(perf_counter() - start)

        samples.sort()
        p95_index = max(0, int(len(samples) * 0.95) - 1)
        p95 = samples[p95_index]
        self.assertLessEqual(p95, 0.75)


if __name__ == "__main__":
    unittest.main()
