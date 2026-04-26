"""Tests for the Whisper STT service wrapper.

Same mocking approach as test_ai_qwen_llm — the wiro_client.run()
boundary is patched so no HTTP egress happens.

Coverage:
    - feature flag gating
    - missing input (no bytes, no URL) → None
    - unsupported language → None
    - bytes path: file uploaded, fields populated correctly
    - URL path: inputAudioUrl set, file slot empty
    - inline transcript path
    - output file URL path with text contenttype
    - non-text outputs are skipped (e.g. processed audio file)
    - PII redaction applied to transcript
    - WiroTaskError → None
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.ai import whisper_stt, wiro_client


def _result(parameters=None, outputs=None):
    return wiro_client.WiroTaskResult(
        task_id="T1",
        socket_token="TKN",
        status="task_postprocess_end",
        parameters=parameters or {},
        outputs=outputs or [],
        elapsed_seconds=15.0,
        total_cost=0.014,
        raw={},
    )


def test_disabled_returns_none():
    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", False), patch(
        "app.services.ai.whisper_stt.run",
        side_effect=AssertionError("run should not be called when disabled"),
    ):
        assert whisper_stt.transcribe(audio_bytes=b"\x00") is None


def test_no_input_returns_none():
    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run",
        side_effect=AssertionError("run should not be called without input"),
    ):
        assert whisper_stt.transcribe() is None


def test_unsupported_language_returns_none():
    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run",
        side_effect=AssertionError("run should not be called for unsupported language"),
    ):
        # SUPPORTED_LANGUAGES is a curated subset; "Klingon" is not in it.
        assert whisper_stt.transcribe(audio_bytes=b"\x00", language="Klingon") is None


def test_bytes_path_uploads_file_and_clears_url():
    captured = {}

    def _capture(model, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"text": "merhaba dünya"})

    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run", side_effect=_capture,
    ):
        whisper_stt.transcribe(audio_bytes=b"audio-content", language="Turkish")

    # File slot populated; URL field cleared (Wiro requires the form
    # shape consistent across both input modes).
    assert captured["files"]["inputAudio"] == ("audio.mp3", b"audio-content", "audio/mpeg")
    assert captured["fields"]["inputAudioUrl"] == ""
    assert captured["fields"]["language"] == "Turkish"


def test_url_path_sets_url_and_empty_file_slot():
    captured = {}

    def _capture(model, fields=None, files=None, **_):  # noqa: ARG001
        captured["fields"] = fields
        captured["files"] = files
        return _result(parameters={"text": "hello"})

    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run", side_effect=_capture,
    ):
        whisper_stt.transcribe(
            audio_url="https://cdn.example/audio.mp3", language="English"
        )

    assert captured["fields"]["inputAudioUrl"] == "https://cdn.example/audio.mp3"
    # File slot still present but empty (multipart shape contract).
    assert captured["files"]["inputAudio"][0] == ""
    assert captured["files"]["inputAudio"][1] == b""


def test_inline_transcript_returned_redacted():
    """PII in the transcript should be redacted before return (default
    redact=True)."""
    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run",
        return_value=_result(parameters={"text": "Adım Ali, telefonum +90 555 123 45 67"}),
    ):
        out = whisper_stt.transcribe(audio_bytes=b"\x00", language="Turkish")
    assert out is not None
    # Phone number should not appear verbatim.
    assert "+90 555 123 45 67" not in out


def test_output_url_text_path_used_when_no_inline_transcript():
    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run",
        return_value=_result(outputs=[
            {"url": "https://cdn/transcript.txt", "contenttype": "text/plain"},
        ]),
    ), patch(
        "app.services.ai.whisper_stt.fetch_output_text",
        return_value="downloaded transcript",
    ):
        out = whisper_stt.transcribe(
            audio_bytes=b"\x00", language="Turkish", redact=False
        )
    assert out == "downloaded transcript"


def test_non_text_outputs_are_skipped():
    """Some Whisper pipelines emit a re-encoded audio alongside the
    transcript. The wrapper must skip non-text outputs and try the
    next one until it finds a text/json file."""
    fetched = []

    def _fetch(url):
        fetched.append(url)
        return "real transcript here"

    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run",
        return_value=_result(outputs=[
            {"url": "https://cdn/processed.mp3", "contenttype": "audio/mpeg"},
            {"url": "https://cdn/transcript.json", "contenttype": "application/json"},
        ]),
    ), patch(
        "app.services.ai.whisper_stt.fetch_output_text", side_effect=_fetch,
    ):
        out = whisper_stt.transcribe(
            audio_bytes=b"\x00", language="Turkish", redact=False
        )

    # Audio output skipped; only the JSON transcript was fetched.
    assert fetched == ["https://cdn/transcript.json"]
    assert out == "real transcript here"


def test_task_error_returns_none():
    with patch.object(whisper_stt.settings, "WIRO_WHISPER_STT_ENABLED", True), patch(
        "app.services.ai.whisper_stt.run",
        side_effect=wiro_client.WiroTaskError("task_cancel"),
    ):
        assert whisper_stt.transcribe(audio_bytes=b"\x00", language="Turkish") is None
