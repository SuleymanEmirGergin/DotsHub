"""Tests for the dots-ocr-1-5 multi-document OCR wrapper.

Mocks ``dots_ocr.run_with_repeated_inputs`` so no HTTP egress.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import dots_ocr, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=3.4,
        total_cost=0.003,
        raw={},
    )


def test_disabled_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", False), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called"),
    ):
        assert dots_ocr.extract(documents=[("a.png", b"\x00", "image/png")]) is None


def test_unsupported_prompt_mode_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called"),
    ):
        assert dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")],
            prompt_mode="not_a_real_mode",
        ) is None


def test_no_documents_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called"),
    ):
        assert dots_ocr.extract(documents=[]) is None
        assert dots_ocr.extract(documents=None) is None


def test_too_many_documents_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=AssertionError("must not be called"),
    ):
        docs = [("d.png", b"\x00", "image/png")] * 51  # cap is 50
        assert dots_ocr.extract(documents=docs) is None


def test_inline_output_returned():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        return_value=_result(parameters={"output": "  Patient: X  "}),
    ):
        out = dots_ocr.extract(documents=[("a.png", b"\x00", "image/png")])
    assert out == "Patient: X"


def test_layout_key_falls_through_to_layout_inline():
    """Layout-mode runs may surface output under different key names."""
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        return_value=_result(parameters={"layout": '{"regions": []}'}),
    ):
        out = dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")],
            prompt_mode="prompt_layout_all_en",
        )
    assert out == '{"regions": []}'


def test_url_fallback_when_no_inline():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        return_value=_result(outputs=[{"url": "https://cdn/o.json"}]),
    ), patch(
        "app.services.ai.dots_ocr.fetch_output_text",
        return_value='{"text": "downloaded"}',
    ):
        out = dots_ocr.extract(documents=[("a.png", b"\x00", "image/png")])
    assert out == '{"text": "downloaded"}'


def test_auth_error_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=wiro_client.WiroAuthError("missing"),
    ):
        assert dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")]
        ) is None


def test_task_error_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")]
        ) is None


def test_timeout_returns_none():
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs",
        side_effect=wiro_client.WiroTimeout("late"),
    ):
        assert dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")]
        ) is None


def test_documents_passed_as_repeated_inputDocumentMultiple():
    captured = {}

    def _capture(model, *, fields, multipart_files, repeated_text=None, timeout=None):  # noqa: ARG001
        captured["fields"] = fields
        captured["multipart_files"] = multipart_files
        captured["repeated_text"] = repeated_text
        return _result(parameters={"output": "ok"})

    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs", side_effect=_capture,
    ):
        dots_ocr.extract(
            documents=[
                ("a.png", b"\x00", "image/png"),
                ("b.png", b"\x01", "image/png"),
                ("c.pdf", b"\x02", "application/pdf"),
            ],
            prompt_mode="prompt_ocr",
        )

    mp = captured["multipart_files"]
    assert len(mp) == 3
    assert all(name == "inputDocumentMultiple" for name, _ in mp)
    # No URL-text repetition for dots-ocr (multifileinput, not combine).
    assert not captured["repeated_text"]


def test_pii_redacted_in_prompt():
    captured = {}

    def _capture(model, *, fields, multipart_files, repeated_text=None, timeout=None):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs", side_effect=_capture,
    ):
        dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")],
            prompt="extract for user@example.com",
            prompt_mode="prompt_ocr",
        )
    assert "user@example.com" not in captured["fields"]["prompt"]


def test_optional_pixel_clamps_only_when_set():
    captured = {}

    def _capture(model, *, fields, multipart_files, repeated_text=None, timeout=None):  # noqa: ARG001
        captured["fields"] = fields
        return _result(parameters={"output": "ok"})

    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs", side_effect=_capture,
    ):
        dots_ocr.extract(
            documents=[("a.png", b"\x00", "image/png")],
            min_pixels=100, max_pixels=2_000_000,
        )
    assert captured["fields"]["minPixels"] == 100
    assert captured["fields"]["maxPixels"] == 2_000_000

    captured.clear()
    with patch.object(dots_ocr.settings, "WIRO_DOTS_OCR_ENABLED", True), patch(
        "app.services.ai.dots_ocr.run_with_repeated_inputs", side_effect=_capture,
    ):
        dots_ocr.extract(documents=[("a.png", b"\x00", "image/png")])
    assert "minPixels" not in captured["fields"]
    assert "maxPixels" not in captured["fields"]
