"""Tests for the Moondream3-Preview VLM wrapper.

Mocks the wiro_client.run() boundary so no HTTP egress happens.
Coverage:
    - feature flag gating
    - empty / whitespace prompt rejected locally
    - missing both image_bytes and image_url → None
    - inline parameters output (``answer`` key)
    - URL-fetch fallback for outputs[].url
    - WiroAuthError / WiroTaskError / WiroTimeout → None
    - PII redaction applied to prompt
    - reasoning flag flipped to "--reasoning" / "" via fields
    - URL-only path puts URL in ``inputImage`` field, not files
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import moondream_vlm, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=0.8,
        total_cost=0.0005,
        raw={},
    )


def test_disabled_returns_none_without_calling_wiro():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", False), patch(
        "app.services.ai.moondream_vlm.run",
        side_effect=AssertionError("must not be called when disabled"),
    ):
        assert moondream_vlm.query(image_bytes=b"\x00", prompt="hi") is None


def test_empty_prompt_returns_none():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        side_effect=AssertionError("must not be called for empty prompt"),
    ):
        assert moondream_vlm.query(image_bytes=b"\x00", prompt="") is None
        assert moondream_vlm.query(image_bytes=b"\x00", prompt="   ") is None


def test_no_image_returns_none():
    """Missing both bytes and URL is a misuse — must short-circuit."""
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        side_effect=AssertionError("must not be called without an image"),
    ):
        assert moondream_vlm.query(prompt="describe") is None


def test_inline_answer_returned():
    """Moondream's primary inline key is ``answer``."""
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        return_value=_result(parameters={"answer": '  {"norwood_stage": 3}  '}),
    ):
        out = moondream_vlm.query(image_bytes=b"\x00", prompt="ask")
    assert out == '{"norwood_stage": 3}'


def test_output_url_fetched_when_no_inline_text():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        return_value=_result(outputs=[{"url": "https://cdn.wiro.ai/m.json"}]),
    ), patch(
        "app.services.ai.moondream_vlm.fetch_output_text",
        return_value='{"answer": "downloaded"}',
    ):
        out = moondream_vlm.query(image_bytes=b"\x00", prompt="ask")
    assert out == '{"answer": "downloaded"}'


def test_auth_error_returns_none():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        side_effect=wiro_client.WiroAuthError("WIRO_API_SECRET empty"),
    ):
        out = moondream_vlm.query(image_bytes=b"\x00", prompt="ask")
    assert out is None


def test_task_error_returns_none():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        out = moondream_vlm.query(image_bytes=b"\x00", prompt="ask")
    assert out is None


def test_timeout_returns_none():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run",
        side_effect=wiro_client.WiroTimeout("polled too long"),
    ):
        out = moondream_vlm.query(image_bytes=b"\x00", prompt="ask")
    assert out is None


def test_pii_redaction_applied_to_prompt():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"answer": "ok"})

    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run", side_effect=_capture,
    ):
        moondream_vlm.query(
            image_bytes=b"\x00",
            prompt="Reach me at user@example.com or +90 555 123 45 67",
        )

    sent_prompt = captured["fields"]["prompt"]
    assert "user@example.com" not in sent_prompt
    assert "+90 555 123 45 67" not in sent_prompt


def test_reasoning_flag_serialised_correctly():
    """reasoning=True → '--reasoning'; reasoning=False → ''. The Wiro
    worker reads this string as a CLI flag passthrough."""
    captured = []

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured.append(fields["reasoning"])
        return _result(parameters={"answer": "ok"})

    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run", side_effect=_capture,
    ):
        moondream_vlm.query(image_bytes=b"\x00", prompt="x", reasoning=True)
        moondream_vlm.query(image_bytes=b"\x00", prompt="x", reasoning=False)

    assert captured == ["--reasoning", ""]


def test_url_only_path_puts_url_in_fields_not_files():
    """The URL path stuffs the URL into the ``inputImage`` text field
    (Moondream's docs show this shape), and DOES NOT pass a file part."""
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"answer": "ok"})

    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run", side_effect=_capture,
    ):
        moondream_vlm.query(image_url="https://example.com/photo.jpg", prompt="ask")

    assert captured["fields"]["inputImage"] == "https://example.com/photo.jpg"
    # files dict should be empty/None — URL goes through fields, not multipart
    assert not captured["files"]


def test_no_output_returns_none():
    with patch.object(moondream_vlm.settings, "WIRO_MOONDREAM_VLM_ENABLED", True), patch(
        "app.services.ai.moondream_vlm.run", return_value=_result(),
    ):
        assert moondream_vlm.query(image_bytes=b"\x00", prompt="ask") is None
