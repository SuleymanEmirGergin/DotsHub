"""Whisper-large-v3-turbo-turkish ASR wrapper via Wiro.ai.

Speech-to-text for patient voice intake. Optimised for Turkish but
auto-detects 50+ languages (TR/EN/DE/RU/AR all supported — same set
as the rest of the platform).

Use cases for health tourism:
  - Patient records a voice message describing symptoms / desired
    procedure → transcribed → fed to procedure_intent for classification
  - Tele-consultation snippet transcription for clinic operator
  - Multilingual intake form audio replacement

Input: audio bytes (multipart upload) or audio URL. Output: transcript
text. Optional speaker diarization for multi-speaker recordings.

PII consideration: audio itself may contain PII (name, address spoken
aloud). The transcript output is redacted by the existing
``app.pii.redact_pii`` helper before being passed to downstream
classifiers. We do NOT redact the audio bytes — that would require
on-the-fly audio processing we don't have.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.pii import redact_pii
from app.services.ai.wiro_client import (
    WiroAuthError,
    WiroTaskError,
    WiroTaskResult,
    WiroTimeout,
    fetch_output_text,
    run,
)

logger = logging.getLogger(__name__)


# Whisper supports 55+ languages per Wiro's enum. We expose the
# patient-facing five plus "auto" — covers all current target
# markets and keeps the public-facing API tight.
SUPPORTED_LANGUAGES = frozenset({
    "auto",
    "Turkish",
    "English",
    "German",
    "Russian",
    "Arabic",
})


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_WHISPER_STT_ENABLED", False))


def transcribe(
    *,
    audio_bytes: Optional[bytes] = None,
    audio_url: Optional[str] = None,
    audio_filename: str = "audio.mp3",
    audio_content_type: str = "audio/mpeg",
    language: str = "auto",
    chunk_length: int = 30,
    batch_size: int = 8,
    num_speakers: int = 1,
    diarization: bool = False,
    max_new_tokens: int = 256,
    timeout: float = 90.0,
    redact: bool = True,
) -> Optional[str]:
    """Transcribe an audio clip via Wiro/Whisper.

    Provide either ``audio_bytes`` (multipart upload) OR ``audio_url``
    (Wiro fetches it from the URL). Bytes path is preferred — patient
    audio shouldn't be on a public URL.

    Args:
        audio_bytes: raw audio file content
        audio_url: alternative: Wiro fetches from this URL
        language: "auto" or one of SUPPORTED_LANGUAGES
        chunk_length: split long audio into N-second chunks for
            batch processing. Default 30s matches Whisper's training.
        batch_size: parallel chunks per inference batch. 8 = balanced.
        num_speakers: 1 unless diarization=True
        diarization: separate speakers in transcript (patient + clinic)
        max_new_tokens: cap on output length
        timeout: poll deadline. Whisper docs say ~20s processing;
            we add headroom for queue + chunked audio.
        redact: apply PII redaction to the returned transcript.
            Default True; pass False only when the caller is the
            redactor itself.

    Returns:
        Transcript text (PII-redacted by default) or None on failure /
        unsupported language / disabled.
    """
    if not is_enabled():
        return None
    if not audio_bytes and not audio_url:
        return None
    if language not in SUPPORTED_LANGUAGES:
        logger.warning("whisper_stt.unsupported_language: %s", language)
        return None

    fields: dict = {
        "language": language,
        "maxNewTokens": max_new_tokens,
        "chunkLength": chunk_length,
        "batchSize": batch_size,
        "numSpeakers": num_speakers,
        # Wiro's CLI flag passthrough — "true"/"false" strings.
        "diarization": "true" if diarization else "false",
    }
    files: dict = {}
    if audio_bytes:
        files["inputAudio"] = (audio_filename, audio_bytes, audio_content_type)
        fields["inputAudioUrl"] = ""
    else:
        fields["inputAudioUrl"] = audio_url
        # Wiro's multipart API still wants the file slot present even
        # in the URL-only path; an empty placeholder keeps the form
        # shape consistent.
        files["inputAudio"] = ("", b"", "application/octet-stream")

    try:
        result = run(
            settings.WIRO_WHISPER_STT_MODEL,
            fields=fields,
            files=files,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("whisper_stt.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("whisper_stt.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("whisper_stt.unexpected: %s", exc)
        return None

    transcript = _extract_transcript(result)
    if transcript and redact:
        transcript = redact_pii(transcript)
    return transcript


def _extract_transcript(result: WiroTaskResult) -> Optional[str]:
    """Whisper output may be inline (small clips) or in an output file
    URL (longer clips with diarization). Probe inline first, then
    download the first text-shaped output."""
    for key in ("transcript", "text", "output"):
        val = (result.parameters or {}).get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    for output in result.outputs:
        url = output.get("url")
        if not url:
            continue
        # Skip non-text outputs (some pipelines emit a re-encoded
        # audio file alongside the transcript). Trust the contenttype
        # header first; fall back to extension probing.
        ct = (output.get("contenttype") or "").lower()
        is_text = (
            "text" in ct
            or "json" in ct
            or url.endswith((".txt", ".json", ".srt", ".vtt"))
        )
        if not is_text:
            continue
        try:
            text = fetch_output_text(url)
        except Exception as exc:  # noqa: BLE001
            logger.info("whisper_stt.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
