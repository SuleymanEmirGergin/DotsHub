"""Soft trigger + high-risk age evaluation.

Soft triggers (e.g. "ense sertliği + yüksek ateş") alone do NOT trigger
EMERGENCY — they collect follow-up questions for the orchestrator. But
soft trigger combined with a high-risk age range (default <6 or >65)
escalates to EMERGENCY: the rule encoded in `rules.json`'s
`age_risk_adjustment.urgency_bias.SAME_DAY_to_ER_NOW_if_soft_redflag`.

`matched_soft_triggers()` is exposed because the orchestrator needs
the list even when no escalation fires (to drive follow-up questions).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.canonical_extract import normalize_text_tr
from app.safety import rules_loader
from app.safety.types import SafetyResult


def is_high_risk_age(age: Optional[int]) -> bool:
    if age is None:
        return False
    cfg = rules_loader.age_risk_config().get("high_risk_ages", {})
    if not cfg:
        return False
    in_a = "min" in cfg and "max" in cfg and cfg["min"] <= age <= cfg["max"]
    in_b = "min2" in cfg and "max2" in cfg and cfg["min2"] <= age <= cfg["max2"]
    return in_a or in_b


def matched_soft_triggers(text_tr: str) -> List[Dict[str, Any]]:
    """Return soft trigger dicts whose keywords appear in `text_tr`."""
    text_norm = normalize_text_tr(text_tr or "")
    if not text_norm:
        return []

    matched: List[Dict[str, Any]] = []
    seen: set = set()
    for trigger in rules_loader.soft_triggers():
        tid = trigger.get("id")
        if tid in seen:
            continue
        for kw in trigger.get("keywords", []):
            kw_norm = normalize_text_tr(kw)
            if kw_norm and kw_norm in text_norm:
                seen.add(tid)
                matched.append(trigger)
                break
    return matched


def evaluate(text_tr: str, age: Optional[int]) -> Optional[SafetyResult]:
    """Combined soft + age. Returns EMERGENCY ONLY when both match.

    Soft-without-high-risk-age returns None here so the deterministic
    contract holds: a SafetyResult with status=EMERGENCY always means
    a hard-stop is required. The package's __init__.check_safety()
    handles the soft-only case (returns OK with `soft_triggers` populated
    so the orchestrator can route follow-up questions).
    """
    matches = matched_soft_triggers(text_tr)
    if not matches:
        return None
    if not is_high_risk_age(age):
        return None

    first = matches[0]
    label = first.get("label", "")
    reason = (
        f"Riskli yaş grubu ({age}) + {label}. "
        f"Temkinli yaklaşım: acil değerlendirme önerilir."
    )
    return SafetyResult(
        status="EMERGENCY",
        rule_id=str(first.get("id", "")),
        reason_tr=reason,
        instructions_tr=list(rules_loader.emergency_instructions_tr()),
        soft_triggers=[str(t.get("id", "")) for t in matches],
        high_risk_age=True,
        path="soft_age",
    )
