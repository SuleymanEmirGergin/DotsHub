"""Tests for the gpt-image-2 image gen/edit/inpaint wrapper.

Mocks ``gpt_image.run`` so no HTTP egress happens.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import gpt_image, wiro_client


def _result(outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters={},
        outputs=outputs or [],
        elapsed_seconds=2.5,
        total_cost=0.012,
        raw={},
    )


def test_disabled_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", False), patch(
        "app.services.ai.gpt_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt_image.generate(prompt="cat") is None


def test_empty_prompt_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt_image.generate(prompt="") is None
        assert gpt_image.generate(prompt="   ") is None


def test_unsupported_size_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt_image.generate(prompt="cat", size="9000x9000") is None


def test_unsupported_quality_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt_image.generate(prompt="cat", quality="ultra") is None


def test_invalid_samples_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt_image.generate(prompt="cat", samples=0) is None
        assert gpt_image.generate(prompt="cat", samples=-1) is None


def test_unsupported_output_format_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert gpt_image.generate(prompt="cat", output_format="bmp") is None


def test_urls_extracted_from_outputs():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        return_value=_result(outputs=[
            {"url": "https://cdn/img-1.png"},
            {"url": "https://cdn/img-2.png"},
        ]),
    ):
        out = gpt_image.generate(prompt="cat")
    assert out == ["https://cdn/img-1.png", "https://cdn/img-2.png"]


def test_empty_outputs_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        return_value=_result(outputs=[]),
    ):
        assert gpt_image.generate(prompt="cat") is None


def test_auth_error_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=wiro_client.WiroAuthError("missing"),
    ):
        assert gpt_image.generate(prompt="cat") is None


def test_task_error_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert gpt_image.generate(prompt="cat") is None


def test_timeout_returns_none():
    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run",
        side_effect=wiro_client.WiroTimeout("late"),
    ):
        assert gpt_image.generate(prompt="cat") is None


def test_pii_redacted_in_prompt():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(outputs=[{"url": "https://cdn/x.png"}])

    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run", side_effect=_capture,
    ):
        gpt_image.generate(prompt="email user@example.com whitening")
    assert "user@example.com" not in captured["fields"]["prompt"]


def test_inpaint_mask_uploaded_when_provided():
    """Mask + image both uploaded as multipart file parts. URL forms
    go to fields. Test the bytes path."""
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(outputs=[{"url": "https://cdn/x.png"}])

    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run", side_effect=_capture,
    ):
        gpt_image.generate(
            prompt="whiten teeth in masked area",
            input_image_bytes=b"\xff\xd8",
            input_image_mask_bytes=b"\x89PNG",
        )

    assert "inputImage" in captured["files"]
    assert "inputImageMask" in captured["files"]


def test_url_inputs_go_to_fields_not_files():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(outputs=[{"url": "https://cdn/x.png"}])

    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run", side_effect=_capture,
    ):
        gpt_image.generate(
            prompt="ask",
            input_image_url="https://example.com/img.jpg",
            input_image_mask_url="https://example.com/mask.png",
        )

    assert captured["fields"]["inputImage"] == "https://example.com/img.jpg"
    assert captured["fields"]["inputImageMask"] == "https://example.com/mask.png"
    assert not captured["files"]


def test_optional_compression_field_only_when_set():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(outputs=[{"url": "https://cdn/x.png"}])

    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run", side_effect=_capture,
    ):
        gpt_image.generate(prompt="cat")
    assert "outputCompression" not in captured["fields"]

    with patch.object(gpt_image.settings, "WIRO_GPT_IMAGE_ENABLED", True), patch(
        "app.services.ai.gpt_image.run", side_effect=_capture,
    ):
        gpt_image.generate(prompt="cat", output_compression=80)
    assert captured["fields"]["outputCompression"] == 80
