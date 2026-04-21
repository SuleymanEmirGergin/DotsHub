"""Unit tests for app.tuning_tasks.

Deterministic rule-based task generation from session dicts.
"""

from __future__ import annotations

import unittest

from app.tuning_tasks import build_tuning_tasks_from_session, extract_tokens


class ExtractTokensTests(unittest.TestCase):
    def test_lowercases_and_filters_short(self):
        out = extract_tokens("Baş AĞRISI ve karıncalanma var")
        self.assertIn("karıncalanma", out)
        # NOTE: "AĞRISI".lower() == "ağrisi" (ASCII I → dotless i).
        self.assertIn("ağrisi", out)
        self.assertNotIn("baş", out)  # 3 chars

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(extract_tokens(""), [])

    def test_none_returns_empty_list(self):
        self.assertEqual(extract_tokens(None), [])  # type: ignore[arg-type]

    def test_punctuation_is_stripped(self):
        out = extract_tokens("abcdef, ghıjkl!!! mnopqr.")
        self.assertEqual(sorted(out), sorted(["abcdef", "ghıjkl", "mnopqr"]))


class BuildTuningTasksKeywordMissingTests(unittest.TestCase):
    def test_missing_keyword_task_created_when_tokens_not_in_canonicals(self):
        session = {
            "id": "s1",
            "input_text": "karıncalanma parıltı şişkinlik",
            "user_canonicals_tr": [],
        }
        tasks = build_tuning_tasks_from_session(session)
        km = [t for t in tasks if t["task_type"] == "KEYWORD_MISSING"]
        self.assertEqual(len(km), 1)
        self.assertEqual(km[0]["severity"], "medium")
        self.assertEqual(km[0]["session_id"], "s1")
        # missed_tokens carry (token, count)
        tokens_in_payload = [t[0] for t in km[0]["payload"]["missed_tokens"]]
        self.assertIn("karıncalanma", tokens_in_payload)

    def test_single_missed_token_below_threshold_no_task(self):
        # Threshold is "len(missed) >= 2", single missed token -> no task.
        session = {
            "id": "s2",
            "input_text": "karıncalanma",
            "user_canonicals_tr": [],
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "KEYWORD_MISSING" for t in tasks))

    def test_tokens_matching_canonical_substring_are_filtered(self):
        session = {
            "id": "s3",
            "input_text": "öksürük başlıyor dinmiyor",
            "user_canonicals_tr": ["öksürük"],
        }
        tasks = build_tuning_tasks_from_session(session)
        km = [t for t in tasks if t["task_type"] == "KEYWORD_MISSING"]
        # "öksürük" is filtered (matches canonical). "başlıyor" + "dinmiyor" remain (2 missed -> task).
        self.assertEqual(len(km), 1)
        payload_tokens = [t[0] for t in km[0]["payload"]["missed_tokens"]]
        self.assertNotIn("öksürük", payload_tokens)

    def test_hardcoded_stopwords_filtered(self):
        # "var", "yok", "evet", "hayır" are inline-filtered stopwords
        # (separate from the free-text stopword list).
        session = {
            "id": "s4",
            "input_text": "var yok evet hayır",
            "user_canonicals_tr": [],
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "KEYWORD_MISSING" for t in tasks))

    def test_payload_contains_existing_canonicals(self):
        session = {
            "id": "s5",
            "input_text": "karıncalanma parıltı şişkinlik",
            "user_canonicals_tr": ["öksürük", "ateş"],
        }
        tasks = build_tuning_tasks_from_session(session)
        km = next(t for t in tasks if t["task_type"] == "KEYWORD_MISSING")
        self.assertEqual(
            sorted(km["payload"]["existing_canonicals"]),
            ["ateş", "öksürük"],
        )


class BuildTuningTasksSpecialtyConfusionTests(unittest.TestCase):
    def test_close_top2_triggers_confusion_task(self):
        session = {
            "id": "s1",
            "input_text": "",
            "specialty_scoring_debug": {
                "top1": {"name_tr": "Kardiyoloji", "final_score": 0.85},
                "top2": {"name_tr": "Göğüs Hastalıkları", "final_score": 0.78},
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        conf = [t for t in tasks if t["task_type"] == "SPECIALTY_CONFUSION"]
        self.assertEqual(len(conf), 1)
        self.assertEqual(conf[0]["severity"], "high")
        # gap = 0.85 - 0.78 = 0.07 < 0.15
        self.assertAlmostEqual(conf[0]["payload"]["gap"], 0.07, places=3)

    def test_wide_gap_no_confusion_task(self):
        session = {
            "id": "s2",
            "input_text": "",
            "specialty_scoring_debug": {
                "top1": {"name_tr": "Kardiyoloji", "final_score": 0.9},
                "top2": {"name_tr": "Ortopedi", "final_score": 0.5},
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "SPECIALTY_CONFUSION" for t in tasks))

    def test_missing_top2_no_confusion(self):
        session = {
            "id": "s3",
            "input_text": "",
            "specialty_scoring_debug": {
                "top1": {"name_tr": "Kardiyoloji", "final_score": 0.9},
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "SPECIALTY_CONFUSION" for t in tasks))

    def test_non_dict_scoring_debug_no_confusion(self):
        session = {
            "id": "s4",
            "input_text": "",
            "specialty_scoring_debug": "invalid",
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "SPECIALTY_CONFUSION" for t in tasks))


class BuildTuningTasksQuestionWeaknessTests(unittest.TestCase):
    def test_low_effectiveness_triggers_weakness_task(self):
        session = {
            "id": "s1",
            "input_text": "",
            "question_selector_debug": {
                "eff_0_1": 0.2,
                "canonical": "göğüs ağrısı",
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        weak = [t for t in tasks if t["task_type"] == "QUESTION_WEAKNESS"]
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0]["severity"], "low")
        self.assertIn("göğüs ağrısı", weak[0]["title"])

    def test_high_effectiveness_no_weakness_task(self):
        session = {
            "id": "s2",
            "input_text": "",
            "question_selector_debug": {
                "eff_0_1": 0.8,
                "canonical": "foo",
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "QUESTION_WEAKNESS" for t in tasks))

    def test_missing_eff_field_no_task(self):
        session = {
            "id": "s3",
            "input_text": "",
            "question_selector_debug": {
                "canonical": "foo",
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "QUESTION_WEAKNESS" for t in tasks))

    def test_non_dict_selector_debug_no_task(self):
        session = {
            "id": "s4",
            "input_text": "",
            "question_selector_debug": ["not", "a", "dict"],
        }
        tasks = build_tuning_tasks_from_session(session)
        self.assertFalse(any(t["task_type"] == "QUESTION_WEAKNESS" for t in tasks))


class BuildTuningTasksIntegrationTests(unittest.TestCase):
    def test_empty_session_yields_empty_task_list(self):
        self.assertEqual(build_tuning_tasks_from_session({}), [])

    def test_all_three_task_types_fire_together(self):
        session = {
            "id": "s1",
            "input_text": "karıncalanma parıltı şişkinlik",
            "user_canonicals_tr": [],
            "specialty_scoring_debug": {
                "top1": {"name_tr": "A", "final_score": 0.8},
                "top2": {"name_tr": "B", "final_score": 0.75},
            },
            "question_selector_debug": {
                "eff_0_1": 0.1,
                "canonical": "zx",
            },
        }
        tasks = build_tuning_tasks_from_session(session)
        types = sorted(t["task_type"] for t in tasks)
        self.assertEqual(
            types,
            ["KEYWORD_MISSING", "QUESTION_WEAKNESS", "SPECIALTY_CONFUSION"],
        )

    def test_task_payload_has_required_fields(self):
        session = {
            "id": "s-abc",
            "input_text": "karıncalanma parıltı şişkinlik",
            "user_canonicals_tr": [],
        }
        tasks = build_tuning_tasks_from_session(session)
        km = next(t for t in tasks if t["task_type"] == "KEYWORD_MISSING")
        for required in ("task_type", "severity", "title", "description", "payload", "session_id"):
            self.assertIn(required, km)
        self.assertEqual(km["session_id"], "s-abc")


if __name__ == "__main__":
    unittest.main()
