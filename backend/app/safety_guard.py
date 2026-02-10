"""Safety guard — deterministic EMERGENCY rule evaluation.

Uses rules.json red_flags.hard_triggers with regex matching.
If a hard trigger fires → EMERGENCY envelope.

Adapted to the actual rules.json format:
  {
    "red_flags": {
      "hard_triggers": [
        { "id": "...", "label": "...", "keywords": [...], "regex": "...", "action": "ER_NOW" },
        ...
      ],
      "emergency_instructions_tr": [...]
    }
  }
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

from app.canonical_extract import normalize_text_tr


def safety_guard_check(
    text_tr: str,
    answers: Dict[str, str],
    rules_json: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Check free text + answers against emergency rules.
    Returns None if safe, or a dict with rule_id/reason_tr/instructions_tr if triggered.
    """
    text_norm = normalize_text_tr(text_tr)

    # Also check answer values (e.g. user typed emergency text as answer)
    for v in (answers or {}).values():
        text_norm += " " + normalize_text_tr(v)

    red_flags = rules_json.get("red_flags", {})
    hard_triggers: List[Dict[str, Any]] = red_flags.get("hard_triggers", [])
    default_instructions: List[str] = red_flags.get(
        "emergency_instructions_tr",
        ["Derhal acil servise başvur veya 112'yi ara."],
    )

    for trigger in hard_triggers:
        triggered = False

        # 1) Try regex first (most precise)
        regex_str = trigger.get("regex")
        if regex_str:
            try:
                if re.search(regex_str, text_norm, flags=re.UNICODE | re.IGNORECASE):
                    triggered = True
            except re.error:
                pass  # malformed regex, fall through to keyword check

        # 2) Keyword fallback
        if not triggered:
            keywords: List[str] = trigger.get("keywords", [])
            for kw in keywords:
                kw_norm = normalize_text_tr(kw)
                if kw_norm and kw_norm in text_norm:
                    triggered = True
                    break

        if triggered:
            return {
                "rule_id": trigger.get("id"),
                "reason_tr": trigger.get("label", "Acil değerlendirme gerekebilir."),
                "instructions_tr": default_instructions,
            }

    return None
