"""LLM fallback for procedure-intent extraction.

When the deterministic synonym matcher (``services/procedure_intent``)
returns ``None`` or a low-confidence match, this module wraps the
existing ``llm_nlu_client`` to ask an LLM to pick one of the known
procedure ids. The model never invents a procedure — the prompt
constrains it to the catalog list.

Why a wrapper, not a fork
    The Wiro/Anthropic/Google client already handles auth, PII
    redaction, and retry. We just shape a procedure-aware prompt and
    parse a constrained JSON response.

Feature flag
    ``LLM_PROCEDURE_INTENT_ENABLED`` (default off). The route handler
    only invokes this fallback when the flag is on AND the
    deterministic match is below
    ``LLM_PROCEDURE_INTENT_MIN_CONFIDENCE``.

Cost & latency
    A real LLM call adds ~1-3s and ~$0.001 per request. Treat this
    layer as a quality nudge for the long tail, not a hot-path
    primary. Most production traffic should still resolve via
    deterministic synonyms.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Optional

from app.core.config import settings
from app.services import procedure_catalog
from app.services.procedure_intent import ProcedureMatch

logger = logging.getLogger(__name__)


# ─── Supabase audit log (mirrors llm_nlu._log_llm_call) ─────────────
#
# Same shape as the existing `llm_calls` table — provider, model,
# tokens, latency, success/error_type, nlu_source label. We piggyback
# on the existing table instead of creating a new one because:
#   - The field set is identical (cost + failure-rate dashboards
#     already query this table; adding new rows is additive)
#   - Operators run a single Grafana panel keyed on llm_calls; a
#     separate table would silently miss procedure-intent traffic
#   - The `nlu_source` label distinguishes the call origin
#     ("procedure_intent_llm") so dashboards can filter
#
# Logging is fire-and-forget on a daemon thread — same trade-off as
# the original: tiny risk of losing the last few rows on shutdown,
# zero risk of slowing the user request path.


def _log_llm_call(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    success: bool,
    error_type: Optional[str],
) -> None:
    """Append one row to llm_calls. No-op when the feature flag is off
    or Supabase isn't configured. Runs in a background thread so the
    triage / quote request returns without waiting on the DB write."""
    if not getattr(settings, "LLM_NLU_LOG_TO_SUPABASE", False):
        return

    row = {
        # Procedure-intent extraction has no session_id at this layer
        # (the route owns that ID; the LLM helper is invoked
        # synchronously inside _resolve_procedure_id without it). The
        # FK column allows NULL — matches the table's ON DELETE SET
        # NULL contract.
        "session_id": None,
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "success": success,
        "error_type": error_type,
        "nlu_source": "procedure_intent_llm",
    }

    def _insert() -> None:
        try:
            from app.db import supabase
            supabase.table("llm_calls").insert(row).execute()
        except Exception as exc:
            logger.warning("procedure_intent_llm.log_failed: %s", exc)

    threading.Thread(target=_insert, daemon=True).start()


# Public knobs — surfaced as module-level functions so tests can patch
# them without monkeying with the singleton client.

def is_enabled() -> bool:
    return bool(getattr(settings, "LLM_PROCEDURE_INTENT_ENABLED", False))


def min_confidence_threshold() -> float:
    return float(getattr(settings, "LLM_PROCEDURE_INTENT_MIN_CONFIDENCE", 0.40))


def should_fallback(deterministic: Optional[ProcedureMatch]) -> bool:
    """Decide whether to invoke the LLM after the deterministic pass.

    Two cases trigger the fallback:
      - No deterministic match at all (``None``)
      - Deterministic match below ``min_confidence_threshold()``

    Both are rare in production (synonym index is wide) so the LLM
    cost stays bounded. Routing a high-confidence match to the LLM
    is a waste — pin that with a unit test below.
    """
    if not is_enabled():
        return False
    if deterministic is None:
        return True
    return deterministic.confidence_0_1 < min_confidence_threshold()


# ─── Prompt construction ─────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "You are a procedure-intent classifier for a health-tourism quote system. "
    "Pick the single best matching procedure id from the provided catalog. "
    "If the user message clearly maps to none of the procedures, answer "
    'with id="none". Never invent ids that are not in the catalog. '
    'Respond with strict JSON only: {"procedure_id": "<id>", '
    '"confidence_0_1": <0.0-1.0>, "reason": "<short>"}'
)


def _build_user_prompt(user_message: str, locale: str | None) -> str:
    """Build the user-side message — catalog + the patient input.

    The catalog is rendered compactly (id + TR/EN name + first 3
    synonyms in the requested locale) so the prompt fits in a small
    token budget. Long synonym lists in the JSON file would balloon
    the prompt without changing the model's accuracy noticeably.
    """
    short_locale = (locale or "tr").split("-")[0].split("_")[0].lower()
    lines = ["CATALOG:"]
    for proc in procedure_catalog.all_procedures():
        names = proc.get("name", {})
        syns = proc.get("synonyms", {}).get(short_locale, [])[:3]
        line = (
            f"- id={proc['id']} | "
            f"tr={names.get('tr', '')} | "
            f"en={names.get('en', '')} | "
            f"hint=[{', '.join(syns)}]"
        )
        lines.append(line)
    lines.append("")
    lines.append(f"USER ({short_locale}): {user_message}")
    return "\n".join(lines)


# ─── Response parsing ────────────────────────────────────────────────


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*?\}", re.MULTILINE)


def _parse_response(raw: str) -> Optional[dict]:
    """Extract the first JSON object from the model output.

    Models occasionally wrap JSON in markdown fences or prose despite
    the strict-JSON instruction. We pull the first ``{...}`` block and
    json.loads it; on parse failure return None and the caller treats
    that as 'LLM did not produce a usable answer'.
    """
    if not raw:
        return None
    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ─── Public extractor ────────────────────────────────────────────────


def extract_via_llm(
    user_message: str, locale: str | None
) -> Optional[ProcedureMatch]:
    """Run the LLM-backed extractor. Returns None on any failure path.

    Failure modes that surface as None:
      - LLM client raises (network, auth, timeout)
      - Response doesn't contain parseable JSON
      - Model returned ``id="none"`` or an id not in the catalog
      - Confidence missing or non-numeric

    The caller (route handler) must treat None as 'still unresolved'
    and return ``PROCEDURE_UNRESOLVED`` to the client; it must NOT
    fall back to the deterministic match again — that already failed.
    """
    if not user_message or not user_message.strip():
        return None

    t_start = time.perf_counter()
    in_tok = 0
    out_tok = 0
    try:
        from app.services.llm_nlu_client import get_nlu_client
        client = get_nlu_client()
        text, in_tok, out_tok = client.call(
            _SYSTEM_PROMPT, _build_user_prompt(user_message, locale)
        )
    except Exception as exc:
        logger.warning(
            "procedure_intent_llm.call_failed: %s; returning None", exc
        )
        # Classify the error coarsely — same buckets the llm_nlu
        # `_health_monitor` uses, so dashboards stay consistent.
        err = type(exc).__name__.lower()
        if "timeout" in err:
            error_type = "timeout"
        elif "ratelimit" in err or "429" in err:
            error_type = "rate_limit"
        elif "httpstatus" in err or "http" in err:
            error_type = "http_error"
        else:
            error_type = "error"
        _log_llm_call(
            provider=getattr(settings, "LLM_PROVIDER", "unknown"),
            model=getattr(settings, "LLM_NLU_MODEL", "unknown"),
            input_tokens=0,
            output_tokens=0,
            latency_ms=int((time.perf_counter() - t_start) * 1000),
            success=False,
            error_type=error_type,
        )
        return None

    latency_ms = int((time.perf_counter() - t_start) * 1000)
    parsed = _parse_response(text)
    if not parsed:
        logger.info("procedure_intent_llm.parse_failed raw=%r", text[:200])
        _log_llm_call(
            provider=getattr(settings, "LLM_PROVIDER", "unknown"),
            model=getattr(settings, "LLM_NLU_MODEL", "unknown"),
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            success=False,
            error_type="schema_error",
        )
        return None

    proc_id = parsed.get("procedure_id")
    if proc_id == "none" or proc_id not in procedure_catalog.procedure_ids():
        # Model gave a parseable answer but rejected the input or
        # hallucinated an unknown id. Counts as a successful call from
        # an infra perspective (no retry warranted) but a "no match"
        # outcome from a product perspective. Logged with success=True
        # so the failure-rate dashboard isn't polluted.
        _log_llm_call(
            provider=getattr(settings, "LLM_PROVIDER", "unknown"),
            model=getattr(settings, "LLM_NLU_MODEL", "unknown"),
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            success=True,
            error_type=None,
        )
        return None

    try:
        confidence = float(parsed.get("confidence_0_1", 0.0))
    except (TypeError, ValueError):
        _log_llm_call(
            provider=getattr(settings, "LLM_PROVIDER", "unknown"),
            model=getattr(settings, "LLM_NLU_MODEL", "unknown"),
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            success=False,
            error_type="schema_error",
        )
        return None
    confidence = max(0.0, min(confidence, 0.95))  # cap mirrors deterministic path

    reason = parsed.get("reason", "")
    _log_llm_call(
        provider=getattr(settings, "LLM_PROVIDER", "unknown"),
        model=getattr(settings, "LLM_NLU_MODEL", "unknown"),
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
        success=True,
        error_type=None,
    )
    return ProcedureMatch(
        procedure_id=proc_id,
        confidence_0_1=round(confidence, 3),
        matched_synonyms=[f"llm:{reason[:60]}"] if reason else ["llm"],
    )
