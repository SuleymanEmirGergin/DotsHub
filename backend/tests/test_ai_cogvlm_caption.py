"""Tests for the CogVLM2 video caption service wrapper.

Same mocking pattern as the other AI service tests.

Coverage:
    - feature flag gating
    - missing input → None
    - bytes path: file uploaded with prompt
    - URL path: inputVideoUrl set, file slot empty
    - HEALTH_TOURISM_PROMPTS preset usable as prompt
    - inline parameters caption
    - output URL fetch
    - PII redaction in prompt
    - WiroTaskError → None
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import cogvlm_caption, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=8.0,
        total_cost=0.005,
        raw={},
    )


def test_disabled_returns_none():
    with patch.object(cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", False), patch(
        "app.services.ai.cogvlm_caption.run",
        side_effect=AssertionError("run should not be called when disabled"),
    ):
        assert cogvlm_caption.caption(video_bytes=b"\x00") is None


def test_no_input_returns_none():
    with patch.object(cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True), patch(
        "app.services.ai.cogvlm_caption.run",
        side_effect=AssertionError("run should not be called without input"),
    ):
        assert cogvlm_caption.caption() is None


def test_bytes_path_uploads_file_and_clears_url():
    captured = {}

    def _capture(model, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"caption": "patient shows visible hairline recession"})

    with patch.object(
        cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True
    ), patch("app.services.ai.cogvlm_caption.run", side_effect=_capture):
        out = cogvlm_caption.caption(
            video_bytes=b"video-content",
            prompt=cogvlm_caption.HEALTH_TOURISM_PROMPTS["hair_loss"],
        )

    assert captured["files"]["inputVideo"] == ("video.mp4", b"video-content", "video/mp4")
    assert captured["fields"]["inputVideoUrl"] == ""
    # The hair_loss preset prompt was forwarded.
    assert "Norwood-scale" in captured["fields"]["prompt"]
    assert out == "patient shows visible hairline recession"


def test_url_path_sets_url_and_empty_file_slot():
    captured = {}

    def _capture(model, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"caption": "ok"})

    with patch.object(
        cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True
    ), patch("app.services.ai.cogvlm_caption.run", side_effect=_capture):
        cogvlm_caption.caption(video_url="https://cdn.example/clip.mp4")

    assert captured["fields"]["inputVideoUrl"] == "https://cdn.example/clip.mp4"
    assert captured["files"]["inputVideo"][0] == ""
    assert captured["files"]["inputVideo"][1] == b""


def test_inline_caption_returned():
    with patch.object(
        cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True
    ), patch(
        "app.services.ai.cogvlm_caption.run",
        return_value=_result(parameters={"caption": "  hairline at temples is recessed  "}),
    ):
        out = cogvlm_caption.caption(video_bytes=b"\x00")
    # Whitespace stripped.
    assert out == "hairline at temples is recessed"


def test_output_url_used_when_no_inline_caption():
    with patch.object(
        cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True
    ), patch(
        "app.services.ai.cogvlm_caption.run",
        return_value=_result(outputs=[{"url": "https://cdn/caption.txt"}]),
    ), patch(
        "app.services.ai.cogvlm_caption.fetch_output_text",
        return_value="from CDN file",
    ):
        out = cogvlm_caption.caption(video_bytes=b"\x00")
    assert out == "from CDN file"


def test_pii_redaction_in_prompt():
    captured = {}

    def _capture(model, fields=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"caption": "ok"})

    with patch.object(
        cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True
    ), patch("app.services.ai.cogvlm_caption.run", side_effect=_capture):
        cogvlm_caption.caption(
            video_bytes=b"\x00",
            prompt="Patient name: Ali, phone +90 555 123 45 67. Describe.",
        )
    assert "+90 555 123 45 67" not in captured["fields"]["prompt"]


def test_task_error_returns_none():
    with patch.object(
        cogvlm_caption.settings, "WIRO_COGVLM_CAPTION_ENABLED", True
    ), patch(
        "app.services.ai.cogvlm_caption.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert cogvlm_caption.caption(video_bytes=b"\x00") is None


def test_health_tourism_prompts_registry_has_expected_keys():
    """A regression guard: removing or renaming a preset breaks any
    route that hard-codes the key. Pin the registry shape."""
    expected = {"hair_loss", "smile_dental", "skin_dermatology", "rhinoplasty_assessment", "general"}
    assert set(cogvlm_caption.HEALTH_TOURISM_PROMPTS) == expected
