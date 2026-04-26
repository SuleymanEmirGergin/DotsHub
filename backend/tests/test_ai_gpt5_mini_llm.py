"""Tests for the gpt-5-mini service wrapper."""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import gpt5_mini_llm, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=1.1,
        total_cost=0.0008,
        raw={},
    )


def test_disabled_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", False), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt5_mini_llm.generate(prompt="hi") is None


def test_empty_prompt_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt5_mini_llm.generate(prompt="") is None
        assert gpt5_mini_llm.generate(prompt="   ") is None


def test_unsupported_reasoning_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt5_mini_llm.generate(prompt="hi", reasoning="extreme") is None


def test_unsupported_verbosity_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt5_mini_llm.generate(prompt="hi", verbosity="loud") is None


def test_inline_output_returned():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        return_value=_result(parameters={"output": "  short answer  "}),
    ):
        assert gpt5_mini_llm.generate(prompt="hi") == "short answer"


def test_url_fetched_when_no_inline():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        return_value=_result(outputs=[{"url": "https://cdn/x.txt"}]),
    ), patch(
        "app.services.ai.gpt5_mini_llm.fetch_output_text",
        return_value="from cdn",
    ):
        assert gpt5_mini_llm.generate(prompt="hi") == "from cdn"


def test_auth_error_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=wiro_client.WiroAuthError("missing"),
    ):
        assert gpt5_mini_llm.generate(prompt="hi") is None


def test_task_error_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert gpt5_mini_llm.generate(prompt="hi") is None


def test_timeout_returns_none():
    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run",
        side_effect=wiro_client.WiroTimeout("late"),
    ):
        assert gpt5_mini_llm.generate(prompt="hi") is None


def test_pii_redacted_in_prompt_and_system():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run", side_effect=_capture,
    ):
        gpt5_mini_llm.generate(
            prompt="phone +90 555 123 45 67",
            system_instructions="reply user@example.com",
        )
    assert "+90 555 123 45 67" not in captured["fields"]["prompt"]
    assert "user@example.com" not in captured["fields"]["systemInstructions"]


def test_websearch_serialised_as_string():
    """Wiro's webSearch is a string enum, not a Python bool. The wrapper
    must convert True/False to 'true'/'false' (lowercase) explicitly so
    capitalised 'True'/'False' don't round-trip a 400."""
    captured = []

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured.append(fields["webSearch"])
        return _result(parameters={"output": "ok"})

    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run", side_effect=_capture,
    ):
        gpt5_mini_llm.generate(prompt="x", web_search=True)
        gpt5_mini_llm.generate(prompt="x", web_search=False)
    assert captured == ["true", "false"]


def test_image_url_goes_to_fields():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"output": "ok"})

    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run", side_effect=_capture,
    ):
        gpt5_mini_llm.generate(prompt="x", input_image_url="https://example.com/i.jpg")
    assert captured["fields"]["inputImage"] == "https://example.com/i.jpg"
    assert not captured["files"]


def test_no_temperature_or_max_tokens_in_payload():
    """Per Wiro schema gpt-5-mini does NOT accept temperature/topP/
    maxOutputTokens; sending them would round-trip 400. Wrapper must
    not include them."""
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(gpt5_mini_llm.settings, "WIRO_GPT5_MINI_LLM_ENABLED", True), patch(
        "app.services.ai.gpt5_mini_llm.run", side_effect=_capture,
    ):
        gpt5_mini_llm.generate(prompt="x")

    sent = captured["fields"]
    assert "temperature" not in sent
    assert "topP" not in sent
    assert "top_p" not in sent
    assert "maxOutputTokens" not in sent
    assert "max_tokens" not in sent
