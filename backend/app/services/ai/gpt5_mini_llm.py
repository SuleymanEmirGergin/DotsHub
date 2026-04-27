"""OpenAI gpt-5-mini multimodal LLM wrapper via Wiro.ai.

Cheaper alternative to Gemini-3-Pro for short summaries / Q&A drafts.
Single optional image, text in, text out. Per Wiro's schema this model
does NOT expose temperature/topP/maxOutputTokens — the cost dial is
``reasoning`` (minimal/low/medium/high) and verbosity controls output
length tier. Higher reasoning + verbosity = more tokens consumed.

Schema (from /v1/Tool/Detail):
  - prompt (textarea, required)
  - inputImage (combinefileinput, optional) — single image
  - user_id (text), session_id (text) — Wiro chat history
  - systemInstructions (textarea) — redacted before send
  - reasoning (select) — "minimal" | "low" | "medium" | "high"
  - webSearch (select) — "false" | "true" (string)
  - verbosity (select) — "low" | "medium" | "high"
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


SUPPORTED_REASONING_LEVELS = frozenset({"minimal", "low", "medium", "high"})
SUPPORTED_VERBOSITY_LEVELS = frozenset({"low", "medium", "high"})


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_GPT5_MINI_LLM_ENABLED", False))


def generate(
    *,
    prompt: str,
    system_instructions: Optional[str] = None,
    input_image_bytes: Optional[bytes] = None,
    input_image_url: Optional[str] = None,
    input_image_filename: str = "img.jpg",
    input_image_content_type: str = "image/jpeg",
    reasoning: str = "low",
    web_search: bool = False,
    verbosity: str = "low",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    timeout: float = 60.0,
) -> Optional[str]:
    """Run gpt-5-mini and return the generated text.

    Args:
        prompt: required, redacted.
        system_instructions: optional, redacted.
        input_image_*: optional single image (combinefileinput).
        reasoning: see SUPPORTED_REASONING_LEVELS. Default "low" keeps
            the cheap path.
        web_search: enable Wiro's web tool. Default off.
        verbosity: see SUPPORTED_VERBOSITY_LEVELS. Default "low" for
            terse output. Bump to "high" for explainers.
        user_id / session_id: Wiro persists chat history; omit for
            stateless calls.
    """
    if not is_enabled():
        return None
    if not prompt or not prompt.strip():
        return None
    if reasoning not in SUPPORTED_REASONING_LEVELS:
        logger.warning("gpt5_mini_llm.unsupported_reasoning: %s", reasoning)
        return None
    if verbosity not in SUPPORTED_VERBOSITY_LEVELS:
        logger.warning("gpt5_mini_llm.unsupported_verbosity: %s", verbosity)
        return None

    fields: dict = {
        "prompt": redact_pii(prompt),
        "reasoning": reasoning,
        # Wiro's webSearch is a string enum, not a bool. Cast carefully
        # so Python's True/False don't serialise as "True"/"False"
        # (capitalised — would round-trip a 400).
        "webSearch": "true" if web_search else "false",
        "verbosity": verbosity,
    }
    if system_instructions:
        fields["systemInstructions"] = redact_pii(system_instructions)
    if user_id:
        fields["user_id"] = user_id
    if session_id:
        fields["session_id"] = session_id

    files: dict = {}
    if input_image_bytes:
        files["inputImage"] = (
            input_image_filename,
            input_image_bytes,
            input_image_content_type,
        )
    elif input_image_url:
        fields["inputImage"] = input_image_url

    try:
        result = run(
            settings.WIRO_GPT5_MINI_LLM_MODEL,
            fields=fields,
            files=files or None,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("gpt5_mini_llm.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("gpt5_mini_llm.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("gpt5_mini_llm.unexpected: %s", exc)
        return None

    return _extract_text(result)


def _extract_text(result: WiroTaskResult) -> Optional[str]:
    """Probe inline parameter keys then fall back to fetching the
    first output URL as text. Mirrors qwen / gemini extraction."""
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
            logger.info("gpt5_mini_llm.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
