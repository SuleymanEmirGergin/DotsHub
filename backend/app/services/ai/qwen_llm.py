"""Qwen3.6-27B LLM wrapper via Wiro.ai.

A 27B dense vision-language model with 262K-token context window.
Used for text generation tasks where the existing Gemini Flash NLU
runner doesn't fit:
  - quote_summary generation (clinic + price → patient-language paragraphs)
  - doctor-Q&A drafts ("what to ask the surgeon about my procedure")
  - multi-language clinic comparison narratives

API: text-in, text-out. PII redacted from user-supplied prompt before
any network call. Failures return None — caller decides whether to
fall back to deterministic copy or surface an error envelope.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.pii import redact_pii
from app.services.ai.wiro_client import (
    WiroTaskError,
    WiroTaskResult,
    WiroTimeout,
    fetch_output_text,
    run,
)

logger = logging.getLogger(__name__)


# ─── Feature gate ────────────────────────────────────────────────────


def is_enabled() -> bool:
    return bool(getattr(settings, "WIRO_QWEN_LLM_ENABLED", False))


# ─── Public API ──────────────────────────────────────────────────────


def generate(
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 0,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    enable_thinking: bool = False,
    timeout: float = 60.0,
) -> Optional[str]:
    """Run Qwen3.6-27B and return the generated text.

    Returns None on any failure path:
      - Feature flag off
      - Empty / whitespace-only prompt
      - Submit/poll raised (network, timeout, task_cancel)
      - Output extraction yielded no text

    Args:
        prompt: User-side text. Redacted before transmission.
        system_prompt: Optional system instructions. Also redacted.
        temperature: 0=deterministic, 1+=creative. 0.7 = sane default.
        max_tokens: 0 means model default (Qwen's default is ~2048).
        user_id / session_id: Wiro persists chat history per
            (user_id, session_id). Pass for multi-turn workflows;
            omit for stateless calls.
        enable_thinking: Wiro flag — adds Qwen's chain-of-thought
            traces to the output. Off by default; turning on costs
            extra tokens with no UX benefit unless we surface the
            thinking explicitly.
    """
    if not is_enabled():
        return None
    if not prompt or not prompt.strip():
        return None

    fields: dict = {
        "prompt": redact_pii(prompt),
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "enableThinking": "true" if enable_thinking else "false",
    }
    if system_prompt:
        fields["system_prompt"] = redact_pii(system_prompt)
    if user_id:
        fields["user_id"] = user_id
    if session_id:
        fields["session_id"] = session_id

    try:
        result = run(
            settings.WIRO_QWEN_LLM_MODEL,
            fields=fields,
            timeout=timeout,
        )
    except (WiroTaskError, WiroTimeout) as exc:
        logger.warning("qwen_llm.task_failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 — never let LLM failures crash callers
        logger.warning("qwen_llm.unexpected: %s", exc)
        return None

    return _extract_text(result)


# ─── Output extraction ──────────────────────────────────────────────


def _extract_text(result: WiroTaskResult) -> Optional[str]:
    """Pull the generated text from the task result.

    Wiro models inconsistently surface output: some inline it in
    ``parameters.output`` (text-only models), others write to a CDN
    file referenced by ``outputs[0].url``. Try inline first (cheap),
    then fetch the first text-shaped output as fallback.
    """
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
            logger.info("qwen_llm.output_fetch_failed url=%s: %s", url, exc)
            continue
        if text and text.strip():
            return text.strip()

    return None
