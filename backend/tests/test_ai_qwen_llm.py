"""Tests for the Qwen3.6-27B service wrapper.

Mocks the wiro_client.run() boundary so no HTTP egress happens. The
wiro_client itself is tested in test_ai_wiro_client.py.

Coverage:
    - feature flag gating (off → returns None without calling Wiro)
    - empty / whitespace prompt short-circuit
    - successful generation (inline parameters path)
    - successful generation via output URL fetch
    - WiroTaskError → None
    - WiroTimeout → None
    - PII redaction applied to user prompt before submit
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import qwen_llm, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=1.2,
        total_cost=0.001,
        raw={},
    )


def test_disabled_returns_none_without_calling_wiro():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", False), patch(
        "app.services.ai.qwen_llm.run",
        side_effect=AssertionError("run should not be called when disabled"),
    ):
        out = qwen_llm.generate(prompt="hello")
    assert out is None


def test_empty_prompt_returns_none():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run",
        side_effect=AssertionError("run should not be called for empty prompt"),
    ):
        assert qwen_llm.generate(prompt="") is None
        assert qwen_llm.generate(prompt="   ") is None


def test_inline_parameters_output_returned():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run",
        return_value=_result(parameters={"output": "  hello world  "}),
    ):
        out = qwen_llm.generate(prompt="hi")
    assert out == "hello world"


def test_output_url_fetched_when_no_inline_text():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run",
        return_value=_result(outputs=[{"url": "https://cdn.wiro.ai/x.txt"}]),
    ), patch(
        "app.services.ai.qwen_llm.fetch_output_text",
        return_value="downloaded result",
    ):
        out = qwen_llm.generate(prompt="hi")
    assert out == "downloaded result"


def test_task_error_returns_none():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        out = qwen_llm.generate(prompt="hi")
    assert out is None


def test_timeout_returns_none():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run",
        side_effect=wiro_client.WiroTimeout("polled too long"),
    ):
        out = qwen_llm.generate(prompt="hi")
    assert out is None


def test_pii_redaction_applied_to_prompt():
    """Phone numbers / emails in the user prompt must be redacted
    BEFORE the network call. We assert by reading the captured fields
    arg passed to run()."""
    captured = []

    def _capture(model, fields=None, **_):  # noqa: ARG001
        captured.append(fields)
        return _result(parameters={"output": "ok"})

    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run", side_effect=_capture,
    ):
        qwen_llm.generate(
            prompt="My phone is +90 555 123 45 67, email me at user@example.com",
        )

    assert len(captured) == 1
    sent_prompt = captured[0]["prompt"]
    # Original PII strings must NOT appear verbatim in what we sent.
    assert "+90 555 123 45 67" not in sent_prompt
    assert "user@example.com" not in sent_prompt


def test_no_output_returns_none():
    with patch.object(qwen_llm.settings, "WIRO_QWEN_LLM_ENABLED", True), patch(
        "app.services.ai.qwen_llm.run", return_value=_result(),
    ):
        assert qwen_llm.generate(prompt="hi") is None
