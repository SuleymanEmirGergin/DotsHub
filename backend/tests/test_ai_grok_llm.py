"""Tests for the grok-4-20 service wrapper."""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import grok_llm, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=1.7,
        total_cost=0.0015,
        raw={},
    )


def test_disabled_returns_none():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", False), patch(
        "app.services.ai.grok_llm.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert grok_llm.generate(prompt="hi") is None


def test_empty_prompt_returns_none():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert grok_llm.generate(prompt="") is None
        assert grok_llm.generate(prompt="   ") is None


def test_inline_output_returned():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run",
        return_value=_result(parameters={"output": "  grok says hi  "}),
    ):
        assert grok_llm.generate(prompt="hi") == "grok says hi"


def test_url_fetched_when_no_inline():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run",
        return_value=_result(outputs=[{"url": "https://cdn/x.txt"}]),
    ), patch(
        "app.services.ai.grok_llm.fetch_output_text",
        return_value="from cdn",
    ):
        assert grok_llm.generate(prompt="hi") == "from cdn"


def test_auth_error_returns_none():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run",
        side_effect=wiro_client.WiroAuthError("missing"),
    ):
        assert grok_llm.generate(prompt="hi") is None


def test_task_error_returns_none():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert grok_llm.generate(prompt="hi") is None


def test_timeout_returns_none():
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run",
        side_effect=wiro_client.WiroTimeout("late"),
    ):
        assert grok_llm.generate(prompt="hi") is None


def test_pii_redacted_in_prompt_and_system():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run", side_effect=_capture,
    ):
        grok_llm.generate(
            prompt="phone +90 555 123 45 67",
            system_instructions="reply user@example.com",
        )
    assert "+90 555 123 45 67" not in captured["fields"]["prompt"]
    assert "user@example.com" not in captured["fields"]["systemInstructions"]


def test_reasoning_and_websearch_serialised_as_strings():
    """Wiro flags are string enums 'true'/'false', not Python bool."""
    captured = []

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured.append((fields["reasoning"], fields["webSearch"]))
        return _result(parameters={"output": "ok"})

    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run", side_effect=_capture,
    ):
        grok_llm.generate(prompt="x", reasoning=True, web_search=True)
        grok_llm.generate(prompt="x", reasoning=False, web_search=False)

    assert captured == [("true", "true"), ("false", "false")]


def test_max_output_tokens_omitted_when_zero():
    """0 means 'use model default' — wrapper must skip the field entirely
    rather than sending '0' which Wiro would interpret as a hard cap."""
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run", side_effect=_capture,
    ):
        grok_llm.generate(prompt="x")
    assert "maxOutputTokens" not in captured["fields"]

    captured.clear()
    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run", side_effect=_capture,
    ):
        grok_llm.generate(prompt="x", max_output_tokens=512)
    assert captured["fields"]["maxOutputTokens"] == 512


def test_image_bytes_uploaded_as_file():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"output": "ok"})

    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run", side_effect=_capture,
    ):
        grok_llm.generate(prompt="x", input_image_bytes=b"\xff\xd8")

    assert "inputImage" in captured["files"]
    assert "inputImage" not in captured["fields"]


def test_image_url_goes_to_fields():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"output": "ok"})

    with patch.object(grok_llm.settings, "WIRO_GROK_LLM_ENABLED", True), patch(
        "app.services.ai.grok_llm.run", side_effect=_capture,
    ):
        grok_llm.generate(prompt="x", input_image_url="https://example.com/i.jpg")
    assert captured["fields"]["inputImage"] == "https://example.com/i.jpg"
    assert not captured["files"]
