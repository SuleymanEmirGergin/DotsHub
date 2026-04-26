"""Tests for the nano-banana-pro image gen wrapper.

Mocks ``nano_banana_image.run`` so no HTTP egress happens. Coverage:

  - feature flag gating
  - empty prompt rejected locally
  - unsupported aspect_ratio / resolution / safety_setting
  - "" aspect_ratio without reference image rejected locally
  - URL extraction from outputs[]
  - auth / task / timeout errors return None
  - PII redaction on prompt
  - empty URL list returns None (vs empty success)
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import nano_banana_image, wiro_client


def _result(outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters={},
        outputs=outputs or [],
        elapsed_seconds=2.0,
        total_cost=0.005,
        raw={},
    )


def test_disabled_returns_none_without_calling_wiro():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", False), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert nano_banana_image.generate(prompt="cat") is None


def test_empty_prompt_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert nano_banana_image.generate(prompt="") is None
        assert nano_banana_image.generate(prompt="   ") is None


def test_unsupported_aspect_ratio_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert nano_banana_image.generate(prompt="cat", aspect_ratio="42:1") is None


def test_unsupported_resolution_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert nano_banana_image.generate(prompt="cat", resolution="100K") is None


def test_unsupported_safety_setting_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert nano_banana_image.generate(prompt="cat", safety_setting="ALLOW_ALL") is None


def test_match_input_aspect_without_reference_rejected():
    """aspect_ratio="" means 'match input' — only valid with a ref image."""
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=AssertionError("must not be called"),
    ):
        assert nano_banana_image.generate(prompt="cat", aspect_ratio="") is None


def test_match_input_aspect_with_url_reference_allowed():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(outputs=[{"url": "https://cdn/img.png"}])

    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run", side_effect=_capture,
    ):
        out = nano_banana_image.generate(
            prompt="brighter teeth", aspect_ratio="",
            reference_image_url="https://example.com/ref.jpg",
        )
    assert out == ["https://cdn/img.png"]
    assert captured["fields"]["inputImage"] == "https://example.com/ref.jpg"


def test_urls_extracted_from_outputs():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        return_value=_result(outputs=[
            {"url": "https://cdn/a.png"},
            {"url": "https://cdn/b.png"},
        ]),
    ):
        out = nano_banana_image.generate(prompt="cat")
    assert out == ["https://cdn/a.png", "https://cdn/b.png"]


def test_empty_outputs_returns_none():
    """No URLs returned = treat as failure (caller None-handles)."""
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        return_value=_result(outputs=[]),
    ):
        assert nano_banana_image.generate(prompt="cat") is None


def test_auth_error_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=wiro_client.WiroAuthError("WIRO_API_SECRET empty"),
    ):
        assert nano_banana_image.generate(prompt="cat") is None


def test_task_error_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert nano_banana_image.generate(prompt="cat") is None


def test_timeout_returns_none():
    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run",
        side_effect=wiro_client.WiroTimeout("polled too long"),
    ):
        assert nano_banana_image.generate(prompt="cat") is None


def test_pii_redacted_in_prompt():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(outputs=[{"url": "https://cdn/x.png"}])

    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run", side_effect=_capture,
    ):
        nano_banana_image.generate(
            prompt="patient user@example.com phone +90 555 123 45 67 wants veneers"
        )

    sent = captured["fields"]["prompt"]
    assert "user@example.com" not in sent
    assert "+90 555 123 45 67" not in sent


def test_bytes_reference_uploaded_as_file_part():
    captured = {}

    def _capture(model, *, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(outputs=[{"url": "https://cdn/x.png"}])

    with patch.object(nano_banana_image.settings, "WIRO_NANO_BANANA_IMAGE_ENABLED", True), patch(
        "app.services.ai.nano_banana_image.run", side_effect=_capture,
    ):
        nano_banana_image.generate(
            prompt="brighter teeth", reference_image_bytes=b"\xff\xd8\xff",
        )

    assert "inputImage" in captured["files"]
    assert "inputImage" not in captured["fields"]
