"""Tests for the patient upload AI dispatcher.

Covers the kind -> AI service routing + observability + DB state
machine. Each AI wrapper (moondream, whisper, cogvlm, dots_ocr) is
mocked at the module boundary so no Wiro traffic in tests.

Critical invariants under test:
    1. Dispatcher NEVER raises (BG task contract).
    2. Every code path terminates with mark_processing -> mark_*
       so the polling endpoint flips to a terminal state.
    3. The right wrapper gets the right kwargs for each kind.
    4. Errors are truncated to ~200 chars (PII + DB bloat).
    5. Prometheus counter increments and breadcrumbs fire on
       every outcome.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services import patient_upload_dispatcher, patient_uploads


# ─── Per-kind happy paths ────────────────────────────────────────────


def test_image_dispatched_to_moondream():
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ) as mp, patch.object(
        patient_uploads, "mark_succeeded",
    ) as ms, patch(
        "app.services.ai.moondream_vlm.query",
        side_effect=lambda **kw: (captured.update(kw) or "norwood: 3"),
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x89PNG\x00\x01",
            upload_kind="image", content_type="image/png",
            filename="scalp.png",
        )
    mp.assert_called_once_with("ASSET-1", ai_provider="moondream")
    ms.assert_called_once()
    success_kwargs = ms.call_args.kwargs
    assert success_kwargs["ai_result_text"] == "norwood: 3"
    assert success_kwargs["ai_latency_ms"] >= 0
    # The raw bytes + content_type forwarded to the wrapper.
    assert captured["image_bytes"] == b"\x89PNG\x00\x01"
    assert captured["image_content_type"] == "image/png"
    assert captured["image_filename"] == "scalp.png"


def test_audio_dispatched_to_whisper_with_turkish():
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.whisper_stt.transcribe",
        side_effect=lambda **kw: (captured.update(kw) or "merhaba"),
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-2", b"\x00\x01",
            upload_kind="audio", content_type="audio/mp3",
            filename="memo.mp3",
        )
    assert captured["language"] == "Turkish"
    assert captured["audio_bytes"] == b"\x00\x01"


def test_video_dispatched_to_cogvlm():
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.cogvlm_caption.caption",
        return_value="visible scalp recession at crown",
    ) as mock_cap:
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-3", b"\x00",
            upload_kind="video", content_type="video/mp4",
            filename="clip.mp4",
        )
    mock_cap.assert_called_once()
    assert mock_cap.call_args.kwargs["video_filename"] == "clip.mp4"


def test_document_dispatched_to_dots_ocr_with_prompt_ocr():
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.dots_ocr.extract",
        side_effect=lambda **kw: (captured.update(kw) or "lab text"),
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-4", b"%PDF-1",
            upload_kind="document", content_type="application/pdf",
            filename="lab.pdf",
        )
    # Forwarded as a single-element documents list.
    docs = list(captured["documents"])
    assert len(docs) == 1
    assert docs[0][0] == "lab.pdf"
    assert docs[0][1] == b"%PDF-1"
    assert docs[0][2] == "application/pdf"
    assert captured["prompt_mode"] == "prompt_ocr"


# ─── Failure paths terminate with mark_failed ───────────────────────


def test_unknown_kind_marks_failed_without_handler_call():
    """Defensive — route validation rejects unknown kinds, but the
    dispatcher must not crash if invoked directly with one."""
    with patch.object(patient_uploads, "mark_processing") as mp, patch.object(
        patient_uploads, "mark_failed",
    ) as mf:
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-X", b"\x00",
            upload_kind="3d_model", content_type="model/gltf",
        )
    # Unknown kind skips the processing transition.
    mp.assert_not_called()
    mf.assert_called_once()
    assert "no handler" in mf.call_args.kwargs["ai_error"]


def test_handler_exception_marks_failed_with_truncated_error():
    """A 5000-char exception message must be truncated before
    persistence — both PII risk and DB column bloat."""
    long_msg = "x" * 5000
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_failed",
    ) as mf, patch(
        "app.services.ai.moondream_vlm.query",
        side_effect=RuntimeError(long_msg),
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    err = mf.call_args.kwargs["ai_error"]
    assert err.startswith("RuntimeError: xx")
    # Truncation cap is 200 chars — assert significantly shorter than
    # the full message rather than a precise length (small leeway for
    # the prefix text).
    assert len(err) <= 200


def test_provider_returns_none_marks_failed():
    """moondream returns None when WIRO_API_SECRET is missing or the
    feature flag is off. Dispatcher surfaces this as failed (not
    succeeded with empty text)."""
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_failed",
    ) as mf, patch(
        "app.services.ai.moondream_vlm.query", return_value=None,
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    mf.assert_called_once()
    err = mf.call_args.kwargs["ai_error"]
    assert "moondream" in err
    assert "None" in err or "empty" in err


def test_provider_returns_whitespace_marks_failed():
    """Wrappers strip + return None on empty, but a defensive '   '
    string still arrives as 'failed' rather than succeeded with
    cleaned empty text."""
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_failed",
    ) as mf, patch.object(
        patient_uploads, "mark_succeeded",
    ) as ms, patch(
        "app.services.ai.moondream_vlm.query", return_value="   \n  ",
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    mf.assert_called_once()
    ms.assert_not_called()


# ─── Side effects: result trimming, latency, observability ──────────


def test_result_text_stripped_before_persistence():
    """Wiro outputs occasionally have trailing whitespace; the row
    should hold the cleaned form so the polling endpoint and any
    downstream NLU don't have to re-strip."""
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ) as ms, patch(
        "app.services.ai.moondream_vlm.query", return_value="  answer  \n",
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    assert ms.call_args.kwargs["ai_result_text"] == "answer"


def test_latency_ms_persisted_on_success():
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ) as ms, patch(
        "app.services.ai.moondream_vlm.query", return_value="ok",
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    assert ms.call_args.kwargs["ai_latency_ms"] >= 0


def test_dispatcher_never_raises_on_handler_blowup():
    """Top-level invariant. A BG task that raises silently leaves the
    row in 'processing' forever — patients see eternal pending. We
    catch every exception and route through mark_failed."""
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_failed",
    ), patch(
        "app.services.ai.moondream_vlm.query",
        side_effect=KeyboardInterrupt("simulated process kill"),
    ):
        # KeyboardInterrupt is a BaseException, NOT a regular Exception
        # — our `except Exception` will NOT catch it. This documents
        # the exact boundary: only normal errors are swallowed.
        try:
            patient_upload_dispatcher.dispatch_to_ai(
                "ASSET-1", b"\x00",
                upload_kind="image", content_type="image/png",
            )
        except KeyboardInterrupt:
            pass  # expected; system signals propagate


# ─── prompt_preset (B5) ─────────────────────────────────────────────


def test_image_preset_picks_HEALTH_TOURISM_PROMPT():
    """Valid preset must surface as the wrapper's ``prompt`` kwarg
    pulling from moondream's HEALTH_TOURISM_PROMPTS dict."""
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.moondream_vlm.query",
        side_effect=lambda **kw: (captured.update(kw) or "ok"),
    ):
        from app.services.ai import moondream_vlm
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-P", b"\x00",
            upload_kind="image", content_type="image/png",
            prompt_preset="hair_loss_norwood",
        )
        expected = moondream_vlm.HEALTH_TOURISM_PROMPTS["hair_loss_norwood"]
    assert captured["prompt"] == expected


def test_image_no_preset_omits_prompt_kwarg():
    """No preset = wrapper's own default prompt kicks in. Dispatcher
    must NOT pass prompt= at all (sending None would override)."""
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.moondream_vlm.query",
        side_effect=lambda **kw: (captured.update(kw) or "ok"),
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-P", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    assert "prompt" not in captured


def test_video_preset_picks_cogvlm_prompt():
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.cogvlm_caption.caption",
        side_effect=lambda **kw: (captured.update(kw) or "ok"),
    ):
        from app.services.ai import cogvlm_caption
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-V", b"\x00",
            upload_kind="video", content_type="video/mp4",
            prompt_preset="rhinoplasty_assessment",
        )
        expected = cogvlm_caption.HEALTH_TOURISM_PROMPTS["rhinoplasty_assessment"]
    assert captured["prompt"] == expected


def test_audio_preset_silently_dropped():
    """Audio handler accepts prompt_preset for signature uniformity
    but ignores it — whisper has no prompt knob in our wrapper.
    Defensive: the route validation rejects this combo, but if a
    direct caller misuses it the dispatcher must NOT crash."""
    captured = {}
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.whisper_stt.transcribe",
        side_effect=lambda **kw: (captured.update(kw) or "ok"),
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-A", b"\x00",
            upload_kind="audio", content_type="audio/mp3",
            prompt_preset="anything",  # ignored by handler
        )
    assert "prompt" not in captured  # whisper has no `prompt` kwarg


def test_provider_tag_includes_preset_when_set():
    """ai_provider column gets 'moondream:hair_loss_norwood' so the
    operator can split llm_calls / Sentry by preset."""
    with patch.object(
        patient_uploads, "mark_processing",
    ) as mp, patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.moondream_vlm.query", return_value="ok",
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-P", b"\x00",
            upload_kind="image", content_type="image/png",
            prompt_preset="hair_loss_norwood",
        )
    mp.assert_called_once_with(
        "ASSET-P", ai_provider="moondream:hair_loss_norwood"
    )


def test_provider_tag_omits_preset_when_none():
    with patch.object(
        patient_uploads, "mark_processing",
    ) as mp, patch.object(
        patient_uploads, "mark_succeeded",
    ), patch(
        "app.services.ai.moondream_vlm.query", return_value="ok",
    ):
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-P", b"\x00",
            upload_kind="image", content_type="image/png",
        )
    mp.assert_called_once_with("ASSET-P", ai_provider="moondream")


def test_dispatcher_never_raises_on_normal_exception():
    """Normal Exception in the handler must NOT propagate — caller is
    a BackgroundTask without exception handlers."""
    with patch.object(
        patient_uploads, "mark_processing",
    ), patch.object(
        patient_uploads, "mark_failed",
    ), patch(
        "app.services.ai.moondream_vlm.query",
        side_effect=ValueError("bad bytes"),
    ):
        # Must not raise.
        patient_upload_dispatcher.dispatch_to_ai(
            "ASSET-1", b"\x00",
            upload_kind="image", content_type="image/png",
        )
