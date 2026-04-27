"""xAI grok-4-20 multimodal LLM wrapper via Wiro.ai.

Companion to gpt-5-mini and Gemini-3-Pro for vendor-redundancy. Unlike
gpt-5-mini, grok-4-20 exposes the classic sampling triple (temperature,
topP, maxOutputTokens) — useful when the integration code needs
deterministic-ish outputs (low temperature) or wants to cap output
length for tight-budget paths.

Schema (from /v1/Tool/Detail):
  - prompt (textarea, required) — redacted
  - inputImage (combinefileinput, optional) — single image (multimodal)
  - user_id (text), session_id (text) — Wiro chat history
  - reasoning (select) — "false" | "true" (string flag)
  - webSearch (select) — "false" | "true"
  - systemInstructions (textarea) — redacted
  - maxOutputTokens (number)
  - temperature (float)
  - topP (float)
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


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_GROK_LLM_ENABLED", False))


def generate(
    *,
    prompt: str,
    system_instructions: Optional[str] = None,
    input_image_bytes: Optional[bytes] = None,
    input_image_url: Optional[str] = None,
    input_image_filename: str = "img.jpg",
    input_image_content_type: str = "image/jpeg",
    reasoning: bool = False,
    web_search: bool = False,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_output_tokens: int = 0,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    timeout: float = 60.0,
) -> Optional[str]:
    """Run grok-4-20 and return the generated text.

    Args:
        prompt: required, redacted.
        system_instructions: optional, redacted.
        input_image_*: optional single image (combinefileinput).
        reasoning: True picks Grok's reasoning variant. Costs more
            tokens; default off for the cheap path.
        web_search: enable Wiro's web tool.
        temperature: 0.0-2.0. 0.7 default — moderate creativity.
        top_p: nucleus sampling. 0.95 default — balanced.
        max_output_tokens: 0 means model default (don't override).
        user_id / session_id: Wiro persists chat history.

    Returns ``None`` on any failure path.
    """
    if not is_enabled():
        return None
    if not prompt or not prompt.strip():
        return None

    fields: dict = {
        "prompt": redact_pii(prompt),
        # Wiro flags are string enums "true"/"false". Cast Python bools
        # explicitly so they don't serialise as "True"/"False".
        "reasoning": "true" if reasoning else "false",
        "webSearch": "true" if web_search else "false",
        "temperature": temperature,
        "topP": top_p,
    }
    if max_output_tokens:
        fields["maxOutputTokens"] = max_output_tokens
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
            settings.WIRO_GROK_LLM_MODEL,
            fields=fields,
            files=files or None,
            timeout=timeout,
        )
    except WiroAuthError as exc:
        logger.error("grok_llm.auth_missing: %s", exc)
        return None
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("grok_llm.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("grok_llm.unexpected: %s", exc)
        return None

    return _extract_text(result)


def _extract_text(result: WiroTaskResult) -> Optional[str]:
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
            logger.info("grok_llm.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
