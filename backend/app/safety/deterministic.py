"""Hard trigger evaluation — deterministic, LLM-bağımsız.

This is the clinical-guarantee layer: a hard match here MUST always
fire regardless of LLM availability or any downstream system. Old
`app/safety_guard.py` and `app/agents/safety_guard.py` had two
slightly divergent hard-eval paths (different normalization, one
searched answers and one didn't). This module unifies on:

- `normalize_text_tr` (Turkish-aware ı/i lowercase) for both regex
  and keyword surfaces. The old top-level used it; the agent used a
  plain `.lower()`. Plain lower() corrupts Turkish on capital İ.
- Search both the symptom text AND any answer values, the way the
  top-level did. The agent path missed answers — a hidden gap if a
  user typed an emergency phrase mid-conversation rather than at the
  start.
- Pre-compiled regex via `rules_loader.compiled_hard_regex()` so
  steady-state cost is cheap.

Order: keyword first (substring scan, shortest path) → regex
(comprehensive). Either match returns immediately.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from app.canonical_extract import normalize_text_tr
from app.safety import rules_loader
from app.safety.types import SafetyResult


def _build_search_text(text_tr: str, answers: Optional[Dict[str, str]]) -> str:
    parts = [normalize_text_tr(text_tr or "")]
    for v in (answers or {}).values():
        parts.append(normalize_text_tr(v or ""))
    return " ".join(p for p in parts if p)


def _check_keywords(search_text: str) -> Optional[Tuple[str, str]]:
    for trigger in rules_loader.hard_triggers():
        for kw in trigger.get("keywords", []):
            kw_norm = normalize_text_tr(kw)
            if kw_norm and kw_norm in search_text:
                return (trigger.get("id", ""), trigger.get("label", ""))
    return None


def _check_regex(search_text: str) -> Optional[Tuple[str, str]]:
    for rule_id, label, pattern in rules_loader.compiled_hard_regex():
        if pattern.search(search_text):
            return (rule_id, label)
    return None


def evaluate(
    text_tr: str, answers: Optional[Dict[str, str]] = None
) -> Optional[SafetyResult]:
    """Hard trigger eval. Returns EMERGENCY SafetyResult on match, None on safe."""
    search_text = _build_search_text(text_tr, answers)
    if not search_text:
        return None

    kw_match = _check_keywords(search_text)
    if kw_match:
        rule_id, label = kw_match
        return SafetyResult(
            status="EMERGENCY",
            rule_id=rule_id,
            reason_tr=label or "Acil değerlendirme gerekebilir.",
            instructions_tr=list(rules_loader.emergency_instructions_tr()),
            path="hard_keyword",
        )

    rx_match = _check_regex(search_text)
    if rx_match:
        rule_id, label = rx_match
        return SafetyResult(
            status="EMERGENCY",
            rule_id=rule_id,
            reason_tr=label or "Acil değerlendirme gerekebilir.",
            instructions_tr=list(rules_loader.emergency_instructions_tr()),
            path="hard_regex",
        )

    return None
