"""Google Gemini-3-Pro multimodal LLM wrapper via Wiro.ai.

Differs from the Qwen3.6-27B wrapper in two ways that matter for
health-tourism use cases:

  1. **Native multimodal input** — accepts up to 50 mixed files
     (images, videos, audio) in a single ``inputAll`` multipart slot.
     Patient sends a few photos of their condition + a voice memo +
     a previous lab scan, and Gemini reads all of it in one call. The
     Qwen wrapper is text-only.

  2. **thinking_level** parameter — Gemini's chain-of-thought budget
     dial. ``minimal`` for cheap categorisation, ``high`` for the
     longer "doctor-readable" quote summary. Operators can tune this
     per use case without code changes.

Use cases this wrapper is for:
  - Quote summary generation that consumes the patient's profile +
    procedure + clinic + their uploaded photos in one call
  - Multi-file medical record interpretation (read patient's PDF lab
    results + their selfie + their voice description, return
    structured findings)
  - "Doctor-Q&A" generation where the model has the full context

PII redaction applies to the prompt + system instructions BEFORE
network call. Files are uploaded as-is — caller is responsible for
ensuring uploaded files don't contain PII the operator hasn't
gathered consent for.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional, Tuple

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


# Gemini-3-Pro accepts up to 50 entries in ``inputAll`` per Wiro's
# OpenAPI definition. We cap caller input at this limit so a misuse
# (e.g. forwarding an entire mobile gallery) fails locally with a
# clear log line instead of round-tripping to Wiro for a 400.
_MAX_INPUT_FILES = 50


# Wiro's enum: minimal / low / medium / high. Pin the set so a typo
# in caller code fails locally instead of silently round-tripping a
# bad value to Wiro.
SUPPORTED_THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high"})


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_GEMINI_LLM_ENABLED", False))


def generate(
    *,
    prompt: str,
    system_instructions: Optional[str] = None,
    input_files: Optional[Iterable[Tuple[str, bytes, str]]] = None,
    input_urls: Optional[Iterable[str]] = None,
    thinking_level: str = "low",
    temperature: float = 1.0,
    top_p: float = 0.95,
    max_output_tokens: int = 65536,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    timeout: float = 90.0,
) -> Optional[str]:
    """Run Gemini-3-Pro and return the generated text.

    Args:
        prompt: Required. User-side text. Redacted before transmission.
        system_instructions: Optional system-level steering. Redacted.
        input_files: Iterable of (filename, content_bytes, content_type)
            tuples. Up to 50 mixed media (images/videos/audio).
        input_urls: Alternative path — Wiro fetches each URL. Mixed
            files + URLs allowed (sum capped at 50).
        thinking_level: One of SUPPORTED_THINKING_LEVELS. Higher
            level → more reasoning tokens → longer wall-time + cost.
            Default "low" keeps the cheap path for routine summaries.
        temperature: 0.0-2.0. Low = deterministic, high = creative.
            Gemini's default is 1.0; clinical descriptions usually
            want 0.3-0.7.
        max_output_tokens: 1-65536. The 65k default is generous; cap
            it lower for tight-budget paths.
        user_id / session_id: Wiro persists chat history per
            (user_id, session_id). Omit for stateless calls.
        timeout: Poll deadline. Wiro lists ~10s for Gemini-3-Pro;
            we add headroom for queue + multi-file preprocessing.

    Returns:
        Generated text, or None on any failure path:
          - Feature flag off
          - Empty / whitespace-only prompt
          - Unsupported thinking_level
          - Too many input files (> 50)
          - WIRO_API_SECRET missing (signature auth required)
          - Submit/poll raised (network, timeout, task_cancel)
          - Output extraction yielded no text
    """
    if not is_enabled():
        return None
    if not prompt or not prompt.strip():
        return None
    if thinking_level not in SUPPORTED_THINKING_LEVELS:
        logger.warning("gemini_llm.unsupported_thinking_level: %s", thinking_level)
        return None

    files_list = list(input_files or [])
    urls_list = list(input_urls or [])
    if len(files_list) + len(urls_list) > _MAX_INPUT_FILES:
        logger.warning(
            "gemini_llm.too_many_inputs: %d (max %d)",
            len(files_list) + len(urls_list),
            _MAX_INPUT_FILES,
        )
        return None

    fields: dict = {
        "prompt": redact_pii(prompt),
        "thinkingLevel": thinking_level,
        "temperature": temperature,
        "topP": top_p,
        "maxOutputTokens": max_output_tokens,
    }
    if system_instructions:
        fields["systemInstructions"] = redact_pii(system_instructions)
    if user_id:
        fields["user_id"] = user_id
    if session_id:
        fields["session_id"] = session_id

    # Wiro's multipart shape for ``inputAll``: each entry is its own
    # form-field with the same name. httpx's ``files=`` dict can't
    # repeat keys, so we use a list of (name, filespec) tuples — httpx
    # accepts that form for repeated multipart parts.
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] = []
    for filename, content, content_type in files_list:
        multipart_files.append(
            ("inputAll", (filename, content, content_type))
        )
    # URL inputs are sent in the same field as plain text values. To
    # preserve repetition with httpx we set them as additional list
    # entries — httpx supports passing a list under ``data=``.
    if urls_list:
        # When URLs are present alongside files, the form needs
        # ``inputAll`` repeated as both file parts AND text parts.
        # httpx accepts a list-of-tuples for ``data`` to allow
        # repeated keys; combine with the files list above.
        url_data = [("inputAll", url) for url in urls_list]
    else:
        url_data = []

    try:
        result = _run_with_repeated_inputs(
            settings.WIRO_GEMINI_LLM_MODEL,
            fields=fields,
            multipart_files=multipart_files,
            url_data=url_data,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("gemini_llm.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("gemini_llm.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("gemini_llm.unexpected: %s", exc)
        return None

    return _extract_text(result)


def _run_with_repeated_inputs(
    model: str,
    *,
    fields: dict,
    multipart_files: list,
    url_data: list,
    timeout: float,
) -> WiroTaskResult:
    """Submit a Gemini task with the repeated-key ``inputAll`` shape,
    then poll. The generic ``wiro_client.run()`` only handles a flat
    fields dict, which can't represent ``inputAll=A&inputAll=B``;
    Gemini-3-Pro is the only model in our catalog that needs this
    repetition, so the small wrapper lives here instead of bloating
    the generic client API."""
    import httpx

    from app.services.ai.wiro_client import (
        _build_result,
        poll,
        require_signature_auth,
    )
    from app.services.llm_nlu_client import _wiro_auth_headers, _wiro_base

    require_signature_auth()

    url = f"{_wiro_base()}/v1/Run/{model}"
    headers = _wiro_auth_headers()

    # Combine flat fields + repeated URL entries into a list-of-pairs
    # that httpx serialises as a multipart form with repeated keys.
    data: list[tuple[str, str]] = list(fields.items())
    data.extend(url_data)
    data = [(k, "" if v is None else str(v)) for k, v in data]

    with httpx.Client(
        timeout=httpx.Timeout(min(timeout, 5.0)), trust_env=False
    ) as c:
        resp = c.post(
            url, headers=headers, data=data, files=multipart_files
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("result", False):
            raise WiroTaskError(
                f"submit returned result=false: errors={body.get('errors')!r}"
            )
        task_id = body.get("taskid")
        if not task_id:
            raise WiroTaskError(f"submit missing taskid: {body}")
        return poll(str(task_id), timeout=timeout, client=c)


def _extract_text(result: WiroTaskResult) -> Optional[str]:
    """Mirror of qwen_llm._extract_text — Wiro is inconsistent about
    where text output lands, so we probe both inline and CDN paths."""
    for key in ("output", "text", "result", "response", "answer"):
        val = (result.parameters or {}).get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    for output in result.outputs:
        url = output.get("url")
        if not url:
            continue
        try:
            text = fetch_output_text(url)
        except Exception as exc:  # noqa: BLE001
            logger.info("gemini_llm.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
