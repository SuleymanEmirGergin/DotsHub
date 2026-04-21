"""Unit tests for app.services.llm_explain.generate_explanation.

Exercises:
  - Feature-flag gate (LLM_EXPLAIN_ENABLED False → empty string)
  - Empty canonicals -> empty string
  - Happy path: mocked NLU client returns short Turkish text
  - Sanity check: too-long output (>=500 chars) -> empty string
  - LLM failure path -> empty string (never raises)
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services import llm_explain


class GenerateExplanationTests(unittest.TestCase):
    def test_returns_empty_when_flag_disabled(self):
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", False):
            out = llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=["göğüs ağrısı"],
            )
        self.assertEqual(out, "")

    def test_returns_empty_when_canonicals_list_empty(self):
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", True):
            out = llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=[],
            )
        self.assertEqual(out, "")

    def test_happy_path_returns_stripped_llm_text(self):
        fake_client = MagicMock()
        fake_client.call.return_value = (
            "  Göğüs ağrınız nedeniyle Kardiyoloji önerilmiştir.  ",
            42, 18,
        )
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", True), \
             patch("app.services.llm_nlu_client.get_nlu_client", return_value=fake_client):
            out = llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=["göğüs ağrısı", "çarpıntı"],
            )
        self.assertEqual(out, "Göğüs ağrınız nedeniyle Kardiyoloji önerilmiştir.")

    def test_empty_llm_output_returns_empty(self):
        fake_client = MagicMock()
        fake_client.call.return_value = ("   ", 1, 0)
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", True), \
             patch("app.services.llm_nlu_client.get_nlu_client", return_value=fake_client):
            out = llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=["x"],
            )
        self.assertEqual(out, "")

    def test_too_long_llm_output_returns_empty(self):
        # 500+ chars triggers the "too long" warning branch.
        fake_client = MagicMock()
        fake_client.call.return_value = ("a" * 600, 100, 200)
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", True), \
             patch("app.services.llm_nlu_client.get_nlu_client", return_value=fake_client):
            out = llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=["x"],
            )
        self.assertEqual(out, "")

    def test_llm_exception_returns_empty_and_swallows(self):
        fake_client = MagicMock()
        fake_client.call.side_effect = RuntimeError("upstream 500")
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", True), \
             patch("app.services.llm_nlu_client.get_nlu_client", return_value=fake_client):
            out = llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=["x"],
            )
        self.assertEqual(out, "")

    def test_symptom_list_is_joined_with_comma_in_user_prompt(self):
        fake_client = MagicMock()
        fake_client.call.return_value = ("ok", 1, 1)
        with patch.object(llm_explain.settings, "LLM_EXPLAIN_ENABLED", True), \
             patch("app.services.llm_nlu_client.get_nlu_client", return_value=fake_client):
            llm_explain.generate_explanation(
                specialty_id="kardiyoloji",
                specialty_name_tr="Kardiyoloji",
                canonicals=["göğüs ağrısı", "çarpıntı"],
            )
        # call(system, user) – second arg should include the comma-joined symptoms.
        _, user_arg = fake_client.call.call_args.args
        self.assertIn("göğüs ağrısı, çarpıntı", user_arg)
        self.assertIn("Kardiyoloji", user_arg)


if __name__ == "__main__":
    unittest.main()
