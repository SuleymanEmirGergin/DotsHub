"""Tests for the LLM fallback in procedure-intent extraction.

Two layers under test:
    1. ``procedure_intent_llm`` module — should_fallback gating,
       prompt construction, response parsing, error handling.
    2. Route integration — when the flag is on and the deterministic
       match is None/low-conf, the route invokes the LLM and uses its
       answer; when the flag is off, the route never calls the LLM.

Every LLM call is mocked. There's no network in these tests.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import procedure_intent, procedure_intent_llm
from app.services.procedure_intent import ProcedureMatch


# ─── should_fallback gating ──────────────────────────────────────────


def test_should_fallback_off_when_flag_disabled():
    with patch.object(procedure_intent_llm.settings,
                      "LLM_PROCEDURE_INTENT_ENABLED", False):
        # Even with no match, the flag-off path returns False.
        assert procedure_intent_llm.should_fallback(None) is False
        match = ProcedureMatch("fue_hair_transplant", 0.1, ["x"])
        assert procedure_intent_llm.should_fallback(match) is False


def test_should_fallback_on_when_flag_enabled_and_no_match():
    with patch.object(procedure_intent_llm.settings,
                      "LLM_PROCEDURE_INTENT_ENABLED", True):
        assert procedure_intent_llm.should_fallback(None) is True


def test_should_fallback_on_when_flag_enabled_and_low_confidence():
    with patch.object(procedure_intent_llm.settings,
                      "LLM_PROCEDURE_INTENT_ENABLED", True), patch.object(
        procedure_intent_llm.settings,
        "LLM_PROCEDURE_INTENT_MIN_CONFIDENCE",
        0.4,
    ):
        match = ProcedureMatch("fue_hair_transplant", 0.2, ["x"])
        assert procedure_intent_llm.should_fallback(match) is True


def test_should_fallback_off_when_flag_enabled_but_high_confidence():
    with patch.object(procedure_intent_llm.settings,
                      "LLM_PROCEDURE_INTENT_ENABLED", True), patch.object(
        procedure_intent_llm.settings,
        "LLM_PROCEDURE_INTENT_MIN_CONFIDENCE",
        0.4,
    ):
        match = ProcedureMatch("fue_hair_transplant", 0.85, ["x"])
        assert procedure_intent_llm.should_fallback(match) is False


# ─── Prompt construction ─────────────────────────────────────────────


def test_user_prompt_includes_catalog_and_user_message():
    out = procedure_intent_llm._build_user_prompt(
        "saçım çok dökülüyor", "tr-TR"
    )
    assert "CATALOG:" in out
    assert "fue_hair_transplant" in out
    assert "saçım çok dökülüyor" in out


def test_user_prompt_locale_changes_synonym_hints():
    tr_prompt = procedure_intent_llm._build_user_prompt("hello", "tr-TR")
    en_prompt = procedure_intent_llm._build_user_prompt("hello", "en-US")
    # Localised hints must differ — TR has "saç ekimi", EN has "hair transplant".
    assert "saç ekimi" in tr_prompt
    assert "hair transplant" in en_prompt


# ─── Response parsing ────────────────────────────────────────────────


def test_parse_response_extracts_first_json_block():
    text = 'Sure, here is the answer: {"procedure_id": "lasik", "confidence_0_1": 0.8, "reason": "matches eye phrasing"}'
    out = procedure_intent_llm._parse_response(text)
    assert out["procedure_id"] == "lasik"
    assert out["confidence_0_1"] == 0.8


def test_parse_response_handles_markdown_fences():
    text = '```json\n{"procedure_id": "rhinoplasty", "confidence_0_1": 0.7}\n```'
    out = procedure_intent_llm._parse_response(text)
    assert out["procedure_id"] == "rhinoplasty"


def test_parse_response_returns_none_on_no_json():
    assert procedure_intent_llm._parse_response("just prose, no JSON") is None
    assert procedure_intent_llm._parse_response("") is None


def test_parse_response_returns_none_on_invalid_json():
    # Open brace but no close — JSON_BLOCK_RE requires balanced braces.
    assert procedure_intent_llm._parse_response("{incomplete") is None


# ─── extract_via_llm ────────────────────────────────────────────────


class _FakeClient:
    def __init__(self, response_text: str):
        self.response = response_text

    def call(self, system, user):  # noqa: ARG002
        return self.response, 100, 50


def test_extract_via_llm_returns_match_on_valid_response():
    fake = _FakeClient(
        '{"procedure_id": "lasik", "confidence_0_1": 0.7, "reason": "eye"}'
    )
    with patch(
        "app.services.llm_nlu_client.get_nlu_client", return_value=fake
    ):
        match = procedure_intent_llm.extract_via_llm(
            "I want laser eye thing", "en-US"
        )
    assert match is not None
    assert match.procedure_id == "lasik"
    assert match.confidence_0_1 == 0.7


def test_extract_via_llm_returns_none_when_id_unknown():
    fake = _FakeClient(
        '{"procedure_id": "magic_pill", "confidence_0_1": 0.99}'
    )
    with patch(
        "app.services.llm_nlu_client.get_nlu_client", return_value=fake
    ):
        assert procedure_intent_llm.extract_via_llm("x", "tr-TR") is None


def test_extract_via_llm_returns_none_on_id_none():
    fake = _FakeClient('{"procedure_id": "none", "confidence_0_1": 0.0}')
    with patch(
        "app.services.llm_nlu_client.get_nlu_client", return_value=fake
    ):
        assert procedure_intent_llm.extract_via_llm("totally unrelated", "tr") is None


def test_extract_via_llm_returns_none_on_client_exception():
    class _Boom:
        def call(self, system, user):  # noqa: ARG002
            raise RuntimeError("network down")

    with patch(
        "app.services.llm_nlu_client.get_nlu_client", return_value=_Boom()
    ):
        assert procedure_intent_llm.extract_via_llm("x", "tr") is None


def test_extract_via_llm_returns_none_on_empty_input():
    # No client call at all — short-circuit before touching the network.
    with patch(
        "app.services.llm_nlu_client.get_nlu_client",
        side_effect=AssertionError("should not be called"),
    ):
        assert procedure_intent_llm.extract_via_llm("", "tr") is None
        assert procedure_intent_llm.extract_via_llm(None, "tr") is None


def test_extract_via_llm_caps_confidence_at_0_95():
    fake = _FakeClient(
        '{"procedure_id": "rhinoplasty", "confidence_0_1": 0.999}'
    )
    with patch(
        "app.services.llm_nlu_client.get_nlu_client", return_value=fake
    ):
        match = procedure_intent_llm.extract_via_llm("x", "tr")
    assert match is not None
    assert match.confidence_0_1 <= 0.95


# ─── Route integration ───────────────────────────────────────────────


class QuoteRouteWithLLMFallbackTests(unittest.TestCase):
    def setUp(self):
        from app import idempotency as idem
        from app import rate_limit as rl

        idem._memory_clear()
        rl._BUCKETS.clear()
        rl._SESSION_BUCKETS.clear()

    def test_flag_off_does_not_invoke_llm(self):
        # With the flag off, even gibberish input must not call the LLM.
        with patch.object(
            procedure_intent_llm.settings,
            "LLM_PROCEDURE_INTENT_ENABLED",
            False,
        ), patch(
            "app.services.llm_nlu_client.get_nlu_client",
            side_effect=AssertionError("LLM should not be called"),
        ):
            with TestClient(app) as client:
                r = client.post("/v1/quote", json={
                    "user_message": "xyzzy plugh quux",
                    "profile": {},
                    "locale": "tr-TR",
                })
        # Returns PROCEDURE_UNRESOLVED, no LLM call.
        self.assertEqual(r.json()["payload"]["code"], "PROCEDURE_UNRESOLVED")

    def test_flag_on_invokes_llm_when_deterministic_misses(self):
        fake = _FakeClient(
            '{"procedure_id": "ivf", "confidence_0_1": 0.6, "reason": "fertility"}'
        )
        with patch.object(
            procedure_intent_llm.settings,
            "LLM_PROCEDURE_INTENT_ENABLED",
            True,
        ), patch(
            "app.services.llm_nlu_client.get_nlu_client", return_value=fake
        ):
            with TestClient(app) as client:
                r = client.post("/v1/quote", json={
                    "user_message": "we are unable to conceive after years",
                    "profile": {},
                    "locale": "en-US",
                })
        body = r.json()
        self.assertEqual(body["type"], "QUOTE")
        self.assertEqual(body["payload"]["procedure"]["id"], "ivf")
        self.assertEqual(
            body["payload"]["intent_resolution"]["resolved_via"], "llm_intent"
        )

    def test_flag_on_does_not_invoke_llm_when_deterministic_high_confidence(self):
        called: list[bool] = []

        class _Tracking:
            def call(self, system, user):  # noqa: ARG002
                called.append(True)
                return '{"procedure_id": "lasik", "confidence_0_1": 0.9}', 0, 0

        with patch.object(
            procedure_intent_llm.settings,
            "LLM_PROCEDURE_INTENT_ENABLED",
            True,
        ), patch(
            "app.services.llm_nlu_client.get_nlu_client",
            return_value=_Tracking(),
        ):
            with TestClient(app) as client:
                # "saç ekimi" is a high-confidence deterministic synonym.
                r = client.post("/v1/quote", json={
                    "user_message": "saç ekimi yaptırmak istiyorum",
                    "profile": {},
                    "locale": "tr-TR",
                })
        self.assertEqual(r.json()["type"], "QUOTE")
        # LLM must not have been called.
        self.assertEqual(called, [])
