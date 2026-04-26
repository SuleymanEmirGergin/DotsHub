"""Tests for the Gemini-3-Pro service wrapper.

Mocks ``gemini_llm._run_with_repeated_inputs`` (the only boundary that
actually does HTTP) so no network egress happens. Coverage:

  - feature flag gating
  - empty / whitespace prompt
  - unsupported thinking_level rejected locally
  - too-many-inputs cap (>50)
  - inline parameters output
  - URL-fetch fallback when no inline text
  - WiroAuthError / WiroTaskError / WiroTimeout → None
  - PII redaction applied to prompt + system instructions
  - inputAll cap honoured against mixed files + URLs
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import gemini_llm, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=1.5,
        total_cost=0.002,
        raw={},
    )


def test_disabled_returns_none_without_calling_wiro():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", False), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called when disabled"),
    ):
        out = gemini_llm.generate(prompt="hello")
    assert out is None


def test_empty_prompt_returns_none():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called for empty prompt"),
    ):
        assert gemini_llm.generate(prompt="") is None
        assert gemini_llm.generate(prompt="   ") is None


def test_unsupported_thinking_level_returns_none():
    """A typo in thinking_level should fail locally, not round-trip
    a bad value to Wiro."""
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called for bad thinking_level"),
    ):
        assert gemini_llm.generate(prompt="hi", thinking_level="ultra") is None


def test_too_many_inputs_returns_none():
    """Caps at 50. Sum of files + URLs must respect the cap."""
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called when over cap"),
    ):
        files = [("f.jpg", b"\x00", "image/jpeg")] * 30
        urls = ["https://x"] * 21  # 30 + 21 = 51 → over cap
        assert gemini_llm.generate(
            prompt="hi", input_files=files, input_urls=urls
        ) is None


def test_inline_parameters_output_returned():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        return_value=_result(parameters={"output": "  inline answer  "}),
    ):
        out = gemini_llm.generate(prompt="hi")
    assert out == "inline answer"


def test_output_url_fetched_when_no_inline_text():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        return_value=_result(outputs=[{"url": "https://cdn.wiro.ai/g.txt"}]),
    ), patch(
        "app.services.ai.gemini_llm.fetch_output_text",
        return_value="downloaded gemini result",
    ):
        out = gemini_llm.generate(prompt="hi")
    assert out == "downloaded gemini result"


def test_auth_error_returns_none():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=wiro_client.WiroAuthError("WIRO_API_SECRET empty"),
    ):
        out = gemini_llm.generate(prompt="hi")
    assert out is None


def test_task_error_returns_none():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        out = gemini_llm.generate(prompt="hi")
    assert out is None


def test_timeout_returns_none():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        side_effect=wiro_client.WiroTimeout("polled too long"),
    ):
        out = gemini_llm.generate(prompt="hi")
    assert out is None


def test_pii_redacted_in_prompt_and_system_instructions():
    """Both fields are user-controlled; both must be redacted before
    network egress."""
    captured = {}

    def _capture(model, *, fields, multipart_files, repeated_text, timeout):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs", side_effect=_capture,
    ):
        gemini_llm.generate(
            prompt="My phone is +90 555 123 45 67",
            system_instructions="Reply to user@example.com only",
        )

    sent_prompt = captured["fields"]["prompt"]
    sent_sys = captured["fields"]["systemInstructions"]
    assert "+90 555 123 45 67" not in sent_prompt
    assert "user@example.com" not in sent_sys


def test_no_output_returns_none():
    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs",
        return_value=_result(),
    ):
        assert gemini_llm.generate(prompt="hi") is None


def test_input_files_passed_as_inputAll_multipart_entries():
    """Each input file becomes a separate multipart entry under the
    same ``inputAll`` key — Wiro's repeated-key shape."""
    captured = {}

    def _capture(model, *, fields, multipart_files, repeated_text, timeout):  # noqa: ARG001
        captured["multipart_files"] = multipart_files
        captured["repeated_text"] = repeated_text
        return _result(parameters={"output": "ok"})

    files = [
        ("a.jpg", b"\x01", "image/jpeg"),
        ("b.png", b"\x02", "image/png"),
    ]
    urls = ["https://example.com/c.mp4"]

    with patch.object(gemini_llm.settings, "WIRO_GEMINI_LLM_ENABLED", True), patch(
        "app.services.ai.gemini_llm.run_with_repeated_inputs", side_effect=_capture,
    ):
        gemini_llm.generate(prompt="describe", input_files=files, input_urls=urls)

    mp = captured["multipart_files"]
    assert len(mp) == 2
    assert all(name == "inputAll" for name, _ in mp)
    assert captured["repeated_text"] == [("inputAll", "https://example.com/c.mp4")]
