"""Safety Guard Agent - Enhanced with rules.json, regex, soft triggers, age risk."""

import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.agents.base import BaseAgent
from app.prompts.system_prompts import SAFETY_GUARD_PROMPT
from app.models.schemas import SafetyGuardOutput

logger = logging.getLogger(__name__)

# ─── Load rules.json ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def _load_rules() -> dict:
    with open(_DATA_DIR / "rules.json", "r", encoding="utf-8") as f:
        return json.load(f)

_rules = _load_rules()
_hard_triggers = _rules["red_flags"]["hard_triggers"]
_soft_triggers = _rules["red_flags"]["soft_triggers"]
_emergency_instructions = _rules["red_flags"]["emergency_instructions_tr"]
_age_risk = _rules["age_risk_adjustment"]

# Pre-compile regex patterns
_compiled_hard_regex: List[tuple] = []
for trigger in _hard_triggers:
    try:
        pattern = re.compile(trigger["regex"], re.IGNORECASE | re.UNICODE)
        _compiled_hard_regex.append((trigger["id"], trigger["label"], pattern))
    except re.error as e:
        logger.warning(f"Invalid regex for trigger {trigger['id']}: {e}")

# Build flat keyword list for fast matching
_hard_keywords: List[tuple] = []
for trigger in _hard_triggers:
    for kw in trigger["keywords"]:
        _hard_keywords.append((kw.lower(), trigger["id"], trigger["label"]))

# Soft keyword list
_soft_keywords: List[tuple] = []
for trigger in _soft_triggers:
    for kw in trigger["keywords"]:
        _soft_keywords.append((kw.lower(), trigger))


def _is_high_risk_age(age: Optional[int]) -> bool:
    """Check if age falls into high-risk range (<6 or >65)."""
    if age is None:
        return False
    ages = _age_risk["high_risk_ages"]
    return (ages["min"] <= age <= ages["max"]) or (ages["min2"] <= age <= ages["max2"])


class SafetyGuardAgent(BaseAgent):
    """Enhanced safety guard with rules.json, regex, soft triggers, and age risk."""

    name = "SafetyGuard"
    system_prompt = SAFETY_GUARD_PROMPT

    def _check_hard_keywords(self, text: str) -> Optional[tuple]:
        """Check hard-coded keywords from rules.json (fast path)."""
        text_lower = text.lower()
        for kw, trigger_id, label in _hard_keywords:
            if kw in text_lower:
                return (trigger_id, label)
        return None

    def _check_hard_regex(self, text: str) -> Optional[tuple]:
        """Check compiled regex patterns from rules.json (comprehensive path)."""
        for trigger_id, label, pattern in _compiled_hard_regex:
            if pattern.search(text):
                return (trigger_id, label)
        return None

    def _check_soft_triggers(self, text: str) -> List[Dict[str, Any]]:
        """Check soft trigger keywords; return matching triggers with follow-up questions."""
        text_lower = text.lower()
        matched = []
        seen_ids = set()
        for kw, trigger in _soft_keywords:
            if kw in text_lower and trigger["id"] not in seen_ids:
                seen_ids.add(trigger["id"])
                matched.append(trigger)
        return matched

    async def run(self, context: dict) -> SafetyGuardOutput:
        """Run safety check with hard/soft triggers, regex, and age-adjusted risk.

        Args:
            context: {
                "user_message": str,
                "symptoms": list,
                "profile": dict,
                "conversation_history": list (optional)
            }
        """
        user_message = context.get("user_message", "")
        profile = context.get("profile", {})
        age = profile.get("age") if profile else None
        high_risk_age = _is_high_risk_age(age)

        # ── Step 1: Hard keyword check (instant, no LLM) ──
        hard_match = self._check_hard_keywords(user_message)
        if hard_match:
            trigger_id, label = hard_match
            logger.warning(f"[SafetyGuard] HARD KEYWORD match: {trigger_id}")
            return SafetyGuardOutput(
                status="EMERGENCY",
                reason=f"Acil durum tespit edildi: {label}",
                emergency_instructions=list(_emergency_instructions),
                missing_info_to_confirm=[],
            )

        # ── Step 2: Hard regex check (comprehensive, no LLM) ──
        regex_match = self._check_hard_regex(user_message)
        if regex_match:
            trigger_id, label = regex_match
            logger.warning(f"[SafetyGuard] HARD REGEX match: {trigger_id}")
            return SafetyGuardOutput(
                status="EMERGENCY",
                reason=f"Acil durum tespit edildi: {label}",
                emergency_instructions=list(_emergency_instructions),
                missing_info_to_confirm=[],
            )

        # ── Step 3: Soft trigger check ──
        soft_matches = self._check_soft_triggers(user_message)
        if soft_matches:
            # If high-risk age + soft trigger → escalate to EMERGENCY
            if high_risk_age:
                first = soft_matches[0]
                logger.warning(f"[SafetyGuard] SOFT trigger + high-risk age → EMERGENCY: {first['id']}")
                return SafetyGuardOutput(
                    status="EMERGENCY",
                    reason=f"Riskli yaş grubu ({age}) + {first['label']}. Temkinli yaklaşım: acil değerlendirme önerilir.",
                    emergency_instructions=list(_emergency_instructions),
                    missing_info_to_confirm=[q for t in soft_matches for q in t["follow_up_questions"]],
                )

            # Otherwise, collect follow-up questions for the soft triggers
            # We still run the LLM check but provide soft trigger context
            follow_ups = []
            for t in soft_matches:
                follow_ups.extend(t["follow_up_questions"])

            # Add soft trigger info to LLM context
            context["soft_triggers_detected"] = [
                {"id": t["id"], "label": t["label"], "follow_up_questions": t["follow_up_questions"]}
                for t in soft_matches
            ]

        # ── Step 4: LLM-based safety check ──
        result = await super().run(context)

        status = result.get("status", "OK")

        # Age risk: if LLM says OK but age is high-risk and there's uncertainty, be more cautious
        missing = result.get("missing_info_to_confirm_tr", result.get("missing_info_to_confirm", []))
        if high_risk_age and status == "OK" and missing:
            logger.info(f"[SafetyGuard] High-risk age ({age}) with missing info → keep OK but flag")

        return SafetyGuardOutput(
            status=status,
            reason=result.get("reason_tr", result.get("reason", "")),
            emergency_instructions=result.get("emergency_instructions_tr", result.get("emergency_instructions", [])),
            missing_info_to_confirm=result.get("missing_info_to_confirm_tr", result.get("missing_info_to_confirm", [])),
        )
