"""Wiro ASR client — openai/whisper-large-v3-turbo-turkish.

Turkish-fine-tuned Whisper variant. Used by /v1/asr/transcribe to
turn a user's recorded audio into the `user_message` text the
triage engine expects.

Why a separate client (instead of extending llm_nlu_client.py):
  - Auth scheme differs. The whisper project on Wiro accepts simple
    `x-api-key` header auth, whereas the gemini-2-5-flash project we
    use for NLU is configured for HMAC-SHA256 signature auth. Same
    WIRO_API_KEY value, different transport — keeping them separate
    keeps each helper readable.
  - Body shape differs. Whisper requires a binary audio upload via
    multipart `inputAudio`; LLM_NLU sends a text `prompt`.
  - Timeouts differ. Whisper processing is ~20s; LLM_NLU is ~3s.

Submit + poll pattern (same as the rest of Wiro):
  1. POST /v1/Run/openai/whisper-large-v3-turbo-turkish
       multipart: inputAudio=<bytes>, language=Turkish, chunkLength=30,
                  batchSize=1, numSpeakers=1
       returns: {taskid, socketaccesstoken}
  2. POST /v1/Task/Detail  {tasktoken: <socketaccesstoken>}
       loop until status in {task_postprocess_end, task_end}
       (or one of the *_error / *_cancel terminals → raise)
  3. Pull transcript out of task.outputs[].url (CDN-served text/json).

PII: audio itself is sensitive. We never persist it on our side —
the bytes flow request→Wiro→discard. Wiro's retention is governed
by their privacy policy (referenced in docs/SUB_PROCESSORS.md).
The transcript IS persisted (as user_message on the triage session
row) since that's what the triage engine consumes downstream.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_WIRO_SUCCESS = {"task_postprocess_end", "task_end"}
_WIRO_ERROR = {"task_error", "task_error_full", "task_cancel", "task_kill"}


def _wiro_base() -> str:
    return settings.WIRO_BASE_URL.rstrip("/")


def _api_key() -> str:
    """Same WIRO_API_KEY used by the NLU client; whisper project
    accepts it as plain x-api-key (no HMAC)."""
    return settings.LLM_API_KEY or settings.WIRO_API_KEY


def _auth_headers() -> dict:
    return {"x-api-key": _api_key()}


def _submit(
    client: httpx.Client,
    model: str,
    audio_bytes: bytes,
    audio_filename: str,
    audio_mime: str,
    language: str = "Turkish",
) -> str:
    """Submit a transcription task. Returns socketaccesstoken."""
    url = f"{_wiro_base()}/v1/Run/{model}"
    files = {
        "inputAudio": (audio_filename, audio_bytes, audio_mime),
        # All four fields are listed as required in the OpenAPI spec.
        # batchSize is typed as string in the spec — keep it as such
        # to match exactly.
        "language": (None, language),
        "chunkLength": (None, "30"),
        "batchSize": (None, "1"),
        "numSpeakers": (None, "1"),
    }
    resp = client.post(url, headers=_auth_headers(), files=files)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("result"):
        raise RuntimeError(f"Wiro ASR submit failed: {body.get('errors')}")
    token = body.get("socketaccesstoken")
    if not token:
        raise RuntimeError(f"Wiro ASR submit missing socketaccesstoken: {body}")
    return token


def _poll(client: httpx.Client, token: str, deadline: float) -> dict:
    """Poll Task/Detail until terminal status. Returns task dict."""
    url = f"{_wiro_base()}/v1/Task/Detail"
    interval = settings.LLM_ASR_POLL_INTERVAL_SECONDS

    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Wiro ASR task timed out after "
                f"{settings.LLM_ASR_TIMEOUT_SECONDS}s"
            )

        resp = client.post(
            url,
            headers={"Content-Type": "application/json", **_auth_headers()},
            json={"tasktoken": token},
        )
        resp.raise_for_status()
        body = resp.json()

        tasks = body.get("tasklist") or []
        if not tasks:
            raise RuntimeError(f"Wiro ASR Task/Detail empty tasklist: {body}")

        task = tasks[0]
        status = str(task.get("status", "")).lower()

        if status in _WIRO_SUCCESS:
            return task
        if status in _WIRO_ERROR:
            raise RuntimeError(
                f"Wiro ASR task failed: status={status}, "
                f"error={str(task.get('debugerror', ''))[:200]}"
            )

        remaining = deadline - time.monotonic()
        sleep_for = min(interval, max(remaining, 0))
        if sleep_for > 0:
            time.sleep(sleep_for)


def _extract_transcript(client: httpx.Client, task: dict) -> str:
    """Pull transcript text out of completed task.

    Whisper outputs are typically a single text/JSON file at
    outputs[0].url. Fall back to inline fields when present.
    """
    # Inline fields first — cheaper if Wiro inlines short transcripts.
    for field in ("debugoutput", "result", "response", "message"):
        v = task.get(field)
        if isinstance(v, str) and v.strip() and not v.strip().startswith("{"):
            return v.strip()

    # Output file (CDN-served). Whisper returns plain text or JSON
    # depending on the project config; we accept both.
    for output in task.get("outputs") or []:
        if not isinstance(output, dict):
            continue
        url = output.get("url")
        if not url:
            continue
        try:
            r = client.get(url, timeout=5.0)
            r.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch ASR output %s: %s", url, exc)
            continue
        ct = str(output.get("contenttype") or "").lower()
        if "json" in ct or r.text.lstrip().startswith("{"):
            try:
                data = r.json()
            except ValueError:
                continue
            # Common Whisper JSON shapes: {"text": ...} or
            # {"transcription": ...} or [{"text": ...}, ...].
            if isinstance(data, dict):
                for key in ("text", "transcription", "transcript"):
                    val = data.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    for key in ("text", "transcription", "transcript"):
                        val = first.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
        # Plain text fallback
        text = r.text.strip()
        if text:
            return text

    raise RuntimeError(
        f"Wiro ASR task completed but no transcript found: {task}"
    )


class ASRClient:
    """Synchronous Wiro ASR client.

    Single public method `transcribe(audio_bytes, ...)` runs the full
    submit+poll cycle within LLM_ASR_TIMEOUT_SECONDS. Raises:
      - TimeoutError on deadline exceeded
      - RuntimeError on Wiro task failure or malformed response
      - httpx.HTTPStatusError on auth / quota errors
    """

    def __init__(
        self,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.model = model or settings.LLM_ASR_MODEL
        self.timeout = (
            timeout if timeout is not None else settings.LLM_ASR_TIMEOUT_SECONDS
        )
        # Per-request HTTP timeout is capped well below the total
        # deadline so a stuck connection can't burn the whole budget.
        self._client = httpx.Client(
            timeout=httpx.Timeout(min(self.timeout, 10.0)),
            trust_env=False,
        )

    def transcribe(
        self,
        audio_bytes: bytes,
        audio_filename: str = "audio.m4a",
        audio_mime: str = "audio/m4a",
        language: str = "Turkish",
    ) -> str:
        """Run ASR end-to-end. Returns the transcript text."""
        deadline = time.monotonic() + self.timeout
        token = _submit(
            self._client,
            self.model,
            audio_bytes,
            audio_filename,
            audio_mime,
            language=language,
        )
        task = _poll(self._client, token, deadline)
        return _extract_transcript(self._client, task)

    def close(self) -> None:
        self._client.close()


_singleton: Optional[ASRClient] = None


def get_asr_client() -> ASRClient:
    """Module-level ASRClient singleton."""
    global _singleton
    if _singleton is None:
        _singleton = ASRClient()
    return _singleton
