"""Automatic speech-to-text — POST /v1/asr/transcribe.

Wraps app/services/asr_client.py (Wiro whisper-large-v3-turbo-turkish)
behind a multipart upload endpoint. Mobile records audio with
expo-av, uploads here, gets a transcript back to prefill the
triage `user_message` field.

Privacy / KVKK / GDPR
---------------------
Audio bytes are sensitive (sağlık verisi). We never persist them on
our side — they flow request → Wiro → discarded. Wiro is listed as
a sub-processor in docs/SUB_PROCESSORS.md; their retention is
governed by their own policy. The transcript is persisted only via
the downstream /v1/triage/turn call (as user_message on the
session row), which already has explicit consent in place.

Cost guard
----------
Wiro charges per GPU-second. A typical 30s clip costs ~$0.03. We
gate on:

  - LLM_ASR_ENABLED feature flag (Fly secret, easy kill switch)
  - LLM_ASR_MAX_BYTES upload cap (10MB → ~5min @16kHz mono)
  - LLM_ASR_DAILY_LIMIT_PER_DEVICE per-device daily cap
  - The shared /v1/ rate-limit middleware (60s/20req per IP)

Failure path
------------
On any Wiro error (timeout, auth, malformed task) the route returns
a typed JSON error (502 / 504) and the mobile UI lets the user
retry or fall back to typing. We never block the user from
proceeding to triage entirely — voice is an enhancement, not a
gate.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asr", tags=["ASR"])


# ─── Per-device daily counter ──────────────────────────────────────
# In-memory deque per device_id, evicting entries older than 24h.
# Multi-instance consistency is lost across workers; that's the same
# trade-off the rest of the rate-limit module accepts (see
# rate_limit.py docstring). For ASR specifically we'd rather under-
# count (let the user through) than reject a legitimate medical
# session, so the in-memory split-brain is acceptable.
_DEVICE_CALLS: Dict[str, Deque[float]] = defaultdict(deque)
_DAY_SEC = 24 * 60 * 60


def _check_device_quota(device_id: str) -> Tuple[bool, int]:
    """Return (allowed, remaining_today)."""
    now = time.monotonic()
    cutoff = now - _DAY_SEC
    q = _DEVICE_CALLS[device_id]
    while q and q[0] < cutoff:
        q.popleft()
    limit = settings.LLM_ASR_DAILY_LIMIT_PER_DEVICE
    if len(q) >= limit:
        return False, 0
    q.append(now)
    return True, limit - len(q)


# ─── Allowed audio MIME types ──────────────────────────────────────
# expo-av on iOS records m4a (AAC), on Android records 3gp/mp4 by
# default. We accept the common set rather than enforce a single
# format — Whisper handles all of them.
_ALLOWED_MIME_PREFIXES = (
    "audio/",
    # Some clients send video/mp4 for AAC-in-MP4 — Whisper accepts
    # the audio track. Allow it explicitly.
    "video/mp4",
)


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(..., description="Recorded audio (m4a/mp3/wav/etc)"),
    device_id: str = Form(..., min_length=1, max_length=128),
    language: str = Form("Turkish", max_length=20),
) -> dict:
    """Transcribe an audio clip.

    Returns: {"transcript": "...", "remaining_today": N}

    Errors (typed):
      - 403 ASR_DISABLED         — feature flag off (mobile should hide UI)
      - 413 AUDIO_TOO_LARGE      — exceeds LLM_ASR_MAX_BYTES
      - 415 UNSUPPORTED_MEDIA    — content-type not audio/*
      - 429 ASR_DAILY_LIMIT      — per-device cap reached
      - 502 ASR_PROVIDER_ERROR   — Wiro returned non-2xx or malformed
      - 504 ASR_TIMEOUT          — submit+poll exceeded deadline
    """
    if not settings.LLM_ASR_ENABLED:
        raise HTTPException(
            status_code=403,
            detail={"code": "ASR_DISABLED", "message": "ASR feature is disabled"},
        )

    # MIME validation. We don't trust client-set content_type fully
    # (it's user-controlled) but it's a cheap first filter; real
    # validation happens in Wiro.
    ct = (audio.content_type or "").lower()
    if not any(ct.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=415,
            detail={
                "code": "UNSUPPORTED_MEDIA",
                "message": f"audio content_type not supported: {ct or 'unknown'}",
            },
        )

    # Size guard — read in one shot since the cap (10MB) is small.
    # FastAPI streams to a SpooledTemporaryFile, so this isn't a
    # full-buffer DoS even for large uploads.
    audio_bytes = await audio.read()
    if len(audio_bytes) > settings.LLM_ASR_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "AUDIO_TOO_LARGE",
                "message": f"audio exceeds {settings.LLM_ASR_MAX_BYTES} bytes",
            },
        )
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_AUDIO", "message": "audio body is empty"},
        )

    # Per-device cap.
    allowed, remaining = _check_device_quota(device_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "ASR_DAILY_LIMIT",
                "message": "daily transcription limit reached for this device",
            },
        )

    # Run the synchronous Wiro client in a worker thread so the
    # event loop isn't blocked during the ~10-30s submit+poll.
    from app.services.asr_client import get_asr_client

    client = get_asr_client()
    started_at = time.monotonic()
    try:
        transcript = await asyncio.to_thread(
            client.transcribe,
            audio_bytes,
            audio.filename or "audio.m4a",
            ct or "audio/m4a",
            language,
        )
    except TimeoutError as exc:
        logger.warning("asr.timeout device=%s elapsed=%.1f", device_id,
                       time.monotonic() - started_at)
        raise HTTPException(
            status_code=504,
            detail={"code": "ASR_TIMEOUT", "message": str(exc)},
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("asr.provider_http_error status=%s body=%s",
                     exc.response.status_code,
                     str(exc.response.text)[:200])
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ASR_PROVIDER_ERROR",
                "message": f"upstream returned {exc.response.status_code}",
            },
        ) from exc
    except Exception as exc:
        logger.exception("asr.failed device=%s", device_id)
        raise HTTPException(
            status_code=502,
            detail={"code": "ASR_PROVIDER_ERROR", "message": str(exc)[:200]},
        ) from exc

    elapsed = time.monotonic() - started_at
    logger.info(
        "asr.ok device=%s bytes=%d elapsed=%.1fs chars=%d",
        device_id, len(audio_bytes), elapsed, len(transcript),
    )
    return {"transcript": transcript, "remaining_today": remaining}
