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
from typing import Optional

from app.core.config import settings
from app.services import procedure_catalog
from app.services.procedure_intent import ProcedureMatch

logger = logging.getLogger(__name__)


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

    try:
        from app.services.llm_nlu_client import get_nlu_client
        client = get_nlu_client()
        text, _, _ = client.call(_SYSTEM_PROMPT, _build_user_prompt(user_message, locale))
    except Exception as exc:
        logger.warning(
            "procedure_intent_llm.call_failed: %s; returning None", exc
        )
        return None

    parsed = _parse_response(text)
    if not parsed:
        logger.info("procedure_intent_llm.parse_failed raw=%r", text[:200])
        return None

    proc_id = parsed.get("procedure_id")
    if proc_id == "none" or proc_id not in procedure_catalog.procedure_ids():
        return None

    try:
        confidence = float(parsed.get("confidence_0_1", 0.0))
    except (TypeError, ValueError):
        return None
    confidence = max(0.0, min(confidence, 0.95))  # cap mirrors deterministic path

    reason = parsed.get("reason", "")
    return ProcedureMatch(
        procedure_id=proc_id,
        confidence_0_1=round(confidence, 3),
        matched_synonyms=[f"llm:{reason[:60]}"] if reason else ["llm"],
    )
