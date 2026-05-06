"""ASR (automatic speech recognition) endpoint — POST /v1/asr/transcribe.

HTTP wrapper around `app.services.ai.whisper_stt.transcribe`. The mobile
client (`mobile/src/api/asrClient.ts`) records m4a audio via expo-av and
posts it here as a multipart upload; we hand the bytes to Wiro/Whisper
and return the transcript shape the client already expects:

    {
      "text": "...",
      "language": "tr",
      "provider": "wiro_whisper",
      "model": "openai/whisper-large-v3-turbo-turkish",
      "duration_ms": 1234
    }

Why a thin wrapper rather than reusing whisper_stt directly: the service
function takes Python args and returns ``Optional[str]``. Surfacing it
as a public route lets us:

- Map ISO language codes (mobile sends "tr") to Whisper's language enum
  ("Turkish") in one place.
- Cap upload size + reject empty files before paying the upstream call.
- Translate Wiro failures into 5xx responses with the
  ``{ code, message_tr }`` shape the mobile alert expects.
- Add per-call duration metrics + breadcrumb-friendly logs without
  every caller of whisper_stt re-implementing them.

Failover: when ``WIRO_WHISPER_STT_ENABLED`` is false (dev / test / Wiro
outage we mute deliberately), we return 503 with a clear ``asr_disabled``
code. The mobile client surfaces this through its existing error
``Alert`` so users fall back to typing instead of seeing silent failure.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.services.ai import whisper_stt

logger = logging.getLogger(__name__)

router = APIRouter()

# Mobile sends ISO codes ("tr"/"en"/"de"/"ru"/"ar"); whisper_stt expects
# Wiro's enum names. "auto" passes through. Anything outside this map
# falls back to "auto" so a misconfigured client still gets a usable
# transcript instead of a 422.
_ISO_TO_WIRO_LANG = {
    "auto": "auto",
    "tr": "Turkish",
    "en": "English",
    "de": "German",
    "ru": "Russian",
    "ar": "Arabic",
}

# 5 MB. At HIGH_QUALITY m4a (~96 kbps) this is ~7 minutes of audio —
# well above the 60s cap the mobile client enforces and below any
# practical Wiro upload limit. Catches accidental binary uploads too.
_MAX_AUDIO_BYTES = 5 * 1024 * 1024


class _ASRError(HTTPException):
    """Helper that produces the ``{ code, message_tr }`` detail shape
    the mobile client already parses out of api errors. Centralising
    this keeps the failure copy consistent across the four exit paths
    below."""

    def __init__(self, status_code: int, code: str, message_tr: str) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message_tr": message_tr},
        )


@router.post("/asr/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe (m4a / mp3 / wav)."),
    language: str = Form(default="tr", description="ISO 639-1 code or 'auto'. Mapped to Whisper's language enum."),
) -> dict:
    """Transcribe a short voice clip.

    The mobile client always sends m4a + ISO language code; the Whisper
    service supports a wider set of containers (mp3 / wav / ogg) but we
    don't try to validate beyond a size cap — Whisper itself rejects
    unsupported formats and we surface that as a 502.

    Returns a ``TranscriptionResult`` shape (text + metadata). The
    caller is the chat textarea: it appends ``text`` to whatever the
    user already typed.
    """
    if not whisper_stt.is_enabled():
        # Configuration-level disable: WIRO_API_KEY not set, or
        # WIRO_WHISPER_STT_ENABLED explicitly off. The mobile alert
        # tells the user to fall back to typing.
        raise _ASRError(
            status_code=503,
            code="asr_disabled",
            message_tr="Sesli giriş şu an kullanılamıyor. Lütfen yazarak devam edin.",
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise _ASRError(
            status_code=400,
            code="empty_audio",
            message_tr="Boş ses dosyası gönderildi. Lütfen tekrar kaydedin.",
        )
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise _ASRError(
            status_code=413,
            code="audio_too_large",
            message_tr="Ses dosyası çok büyük (en fazla 5 MB).",
        )

    # Map ISO code → Wiro enum. Unrecognised inputs degrade to "auto"
    # rather than rejecting — Whisper's autodetect is solid for our
    # five-language target set, and the alternative is a confusing
    # 422 the mobile alert can't action.
    iso = (language or "tr").lower().strip()
    wiro_lang = _ISO_TO_WIRO_LANG.get(iso, "auto")

    started = time.monotonic()
    transcript: Optional[str] = whisper_stt.transcribe(
        audio_bytes=audio_bytes,
        audio_filename=audio.filename or "recording.m4a",
        audio_content_type=audio.content_type or "audio/m4a",
        language=wiro_lang,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    if transcript is None:
        # Wiro upstream failure (auth / rate-limit / timeout) —
        # whisper_stt swallows the specific exception and logs it,
        # so we just know "didn't work." 502 conveys "your request
        # was fine, an upstream we depend on is broken."
        logger.warning(
            "asr.transcribe_failed lang=%s bytes=%d duration_ms=%d",
            wiro_lang,
            len(audio_bytes),
            duration_ms,
        )
        raise _ASRError(
            status_code=502,
            code="asr_failed",
            message_tr="Ses kaydı işlenemedi. Lütfen yazarak deneyin.",
        )

    logger.info(
        "asr.transcribe_ok lang=%s bytes=%d duration_ms=%d transcript_len=%d",
        wiro_lang,
        len(audio_bytes),
        duration_ms,
        len(transcript),
    )

    return {
        "text": transcript,
        # Echo the original ISO code rather than the Wiro enum so
        # callers don't have to map back. "auto" stays "auto".
        "language": iso if wiro_lang != "auto" else "auto",
        "provider": "wiro_whisper",
        "model": settings.WIRO_WHISPER_STT_MODEL,
        "duration_ms": duration_ms,
    }
