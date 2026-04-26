"""AI dispatcher for patient uploads.

Wires the upload route to the right Wiro AI wrapper based on
``upload_kind``. The route schedules a BackgroundTask that calls
``dispatch_to_ai``; this module owns:

  - kind-to-service routing (image -> moondream, audio -> whisper,
    video -> cogvlm, document -> dots_ocr)
  - Prometheus / Sentry observability per attempt
  - Status updates on the patient_uploads row via
    ``patient_uploads.mark_*``

Critical contract: NEVER raise. The route schedules this on a
BackgroundTask so it inherits no request scope; an unhandled
exception would surface as a generic event without context, and the
patient's row would be stuck in "processing" forever. Every failure
mode terminates with ``mark_failed`` + a metric tick.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from app.observability.metrics import (
    patient_upload_latency_seconds,
    patient_upload_total,
)
from app.services import patient_uploads

logger = logging.getLogger(__name__)


# ─── Handler registry ───────────────────────────────────────────────
#
# Lazy imports inside each handler keep the dispatcher's import graph
# light; tests can stub a single AI service by patch.object without
# pulling every Wiro wrapper into the test process.


def _handle_image(
    content: bytes, *, content_type: str, filename: str,
) -> Optional[str]:
    """Image -> moondream VLM. Default prompt is the generic clinical
    description; callers wanting a steered preset (Norwood / smile /
    dermatology) will need a richer route signature later — for the
    initial wire-through, generic is enough to validate the pipe."""
    from app.services.ai import moondream_vlm

    return moondream_vlm.query(
        image_bytes=content,
        image_filename=filename or "image.jpg",
        image_content_type=content_type,
    )


def _handle_audio(
    content: bytes, *, content_type: str, filename: str,
) -> Optional[str]:
    """Audio -> whisper STT. Turkish-tuned model handles ~50 languages
    (auto-detect inside Wiro); we ship Turkish as the default since
    that's the primary patient locale."""
    from app.services.ai import whisper_stt

    return whisper_stt.transcribe(
        audio_bytes=content,
        audio_filename=filename or "audio.mp3",
        audio_content_type=content_type,
        language="Turkish",
    )


def _handle_video(
    content: bytes, *, content_type: str, filename: str,
) -> Optional[str]:
    """Video -> cogvlm caption. Generic prompt for the initial wire-
    through; clinical-domain prompt presets live in
    cogvlm_caption.HEALTH_TOURISM_PROMPTS for callers that want them."""
    from app.services.ai import cogvlm_caption

    return cogvlm_caption.caption(
        video_bytes=content,
        video_filename=filename or "video.mp4",
        video_content_type=content_type,
    )


def _handle_document(
    content: bytes, *, content_type: str, filename: str,
) -> Optional[str]:
    """Document -> dots-ocr. ``prompt_ocr`` mode returns plain text;
    layout-aware modes (``prompt_layout_all_en``) return JSON-shaped
    region/box/class structures that downstream code can parse."""
    from app.services.ai import dots_ocr

    return dots_ocr.extract(
        documents=[(filename or "doc", content, content_type)],
        prompt_mode="prompt_ocr",
    )


# (provider_label, handler_fn) — provider_label lands on the row's
# ai_provider column AND on the Sentry breadcrumb. Adding a new kind
# is one entry here + a route validator entry + a service file.
_HANDLERS: dict[str, tuple[str, Callable[..., Optional[str]]]] = {
    "image": ("moondream", _handle_image),
    "audio": ("whisper", _handle_audio),
    "video": ("cogvlm", _handle_video),
    "document": ("dots_ocr", _handle_document),
}


# ─── Sentry breadcrumb (best-effort) ────────────────────────────────


def _sentry_breadcrumb(
    *,
    asset_id: str,
    kind: str,
    provider: str,
    outcome: str,
    latency_ms: int,
    error: Optional[str] = None,
) -> None:
    """Background tasks don't inherit the request scope, so any
    unhandled crash would surface without context. Crumbs added here
    keep the trail intact when an exception eventually fires —
    matching the pattern in services/quote_summary.py."""
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            category="patient_upload_dispatcher",
            message=f"asset={asset_id[:8]} kind={kind} provider={provider} outcome={outcome}",
            level="info" if outcome == "success" else "warning",
            data={
                "asset_id": asset_id,
                "kind": kind,
                "provider": provider,
                "outcome": outcome,
                "latency_ms": latency_ms,
                "error": (error or "")[:200],
            },
        )
    except Exception:  # noqa: BLE001 — observability must not raise
        pass


# ─── Public dispatcher ──────────────────────────────────────────────


def dispatch_to_ai(
    asset_id: str,
    content_bytes: bytes,
    *,
    upload_kind: str,
    content_type: str,
    filename: str = "",
) -> None:
    """Run the kind-appropriate AI service against ``content_bytes``
    and write the result back to the patient_uploads row.

    Idempotent in the sense that re-running it on a row already in a
    terminal state (succeeded/failed) overwrites the previous result —
    callers shouldn't do that, but no protection is in place because
    BackgroundTasks fires once per /upload by construction.

    All failure paths terminate with ``patient_uploads.mark_failed``
    so the polling endpoint flips to a terminal state. Errors are
    truncated to 200 chars before persistence — never persist a
    multi-line traceback (PII risk + DB bloat).
    """
    t_start = time.perf_counter()

    handler_entry = _HANDLERS.get(upload_kind)
    if handler_entry is None:
        # Defensive: route validation rejects unknown kinds; this
        # branch only fires if the dispatcher is invoked directly.
        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        patient_upload_total.labels(kind=upload_kind, outcome="skipped").inc()
        _sentry_breadcrumb(
            asset_id=asset_id, kind=upload_kind, provider="-",
            outcome="skipped", latency_ms=elapsed_ms,
            error=f"no handler for kind={upload_kind}",
        )
        patient_uploads.mark_failed(
            asset_id,
            ai_error=f"no handler for kind={upload_kind}",
            ai_latency_ms=elapsed_ms,
        )
        return

    provider, handler_fn = handler_entry
    patient_uploads.mark_processing(asset_id, ai_provider=provider)

    try:
        result_text = handler_fn(
            content_bytes,
            content_type=content_type,
            filename=filename,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the BG task
        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        patient_upload_total.labels(kind=upload_kind, outcome="error").inc()
        patient_upload_latency_seconds.labels(kind=upload_kind).observe(
            elapsed_ms / 1000.0
        )
        err_text = f"{type(exc).__name__}: {exc}"[:200]
        logger.warning(
            "patient_upload_dispatcher.handler_raised asset_id=%s kind=%s: %s",
            asset_id, upload_kind, exc,
        )
        _sentry_breadcrumb(
            asset_id=asset_id, kind=upload_kind, provider=provider,
            outcome="error", latency_ms=elapsed_ms, error=err_text,
        )
        patient_uploads.mark_failed(
            asset_id, ai_error=err_text, ai_latency_ms=elapsed_ms,
        )
        return

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    patient_upload_latency_seconds.labels(kind=upload_kind).observe(
        elapsed_ms / 1000.0
    )

    if not result_text or not result_text.strip():
        patient_upload_total.labels(kind=upload_kind, outcome="empty").inc()
        _sentry_breadcrumb(
            asset_id=asset_id, kind=upload_kind, provider=provider,
            outcome="empty", latency_ms=elapsed_ms,
            error="provider returned None or empty",
        )
        patient_uploads.mark_failed(
            asset_id,
            ai_error=(
                f"{provider} returned None or empty. Likely causes: "
                "WIRO_*_ENABLED off, WIRO_API_SECRET missing, or "
                "Wiro task_error. Check llm_calls / Sentry."
            ),
            ai_latency_ms=elapsed_ms,
        )
        return

    cleaned = result_text.strip()
    patient_upload_total.labels(kind=upload_kind, outcome="success").inc()
    _sentry_breadcrumb(
        asset_id=asset_id, kind=upload_kind, provider=provider,
        outcome="success", latency_ms=elapsed_ms,
    )
    patient_uploads.mark_succeeded(
        asset_id, ai_result_text=cleaned, ai_latency_ms=elapsed_ms,
    )
