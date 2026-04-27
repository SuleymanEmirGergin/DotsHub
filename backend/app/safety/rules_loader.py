"""rules.json loader with module-level caching.

Loads `backend/app/data/rules.json` once and caches the parsed dict
+ pre-compiled hard regex list. The old `app/agents/safety_guard.py`
loaded + compiled at module import; `app/safety_guard.py` re-parsed
the rules JSON every call. We compile once on first access (lazy) so
import-time JSON failures degrade to a runtime error at the first
safety check rather than crashing the whole app on cold start.

Tests can call `reset_cache()` between runs to pick up a freshly
written rules.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_RULES_PATH = _DATA_DIR / "rules.json"

_rules_cache: Dict[str, Any] | None = None
_compiled_regex_cache: List[Tuple[str, str, "re.Pattern[str]"]] | None = None


def _load() -> Dict[str, Any]:
    global _rules_cache
    if _rules_cache is None:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            _rules_cache = json.load(f)
    return _rules_cache


def hard_triggers() -> List[Dict[str, Any]]:
    return _load().get("red_flags", {}).get("hard_triggers", [])


def soft_triggers() -> List[Dict[str, Any]]:
    return _load().get("red_flags", {}).get("soft_triggers", [])


def emergency_instructions_tr() -> List[str]:
    return _load().get("red_flags", {}).get(
        "emergency_instructions_tr",
        ["Derhal acil servise başvur veya 112'yi ara."],
    )


def age_risk_config() -> Dict[str, Any]:
    return _load().get("age_risk_adjustment", {})


def compiled_hard_regex() -> List[Tuple[str, str, "re.Pattern[str]"]]:
    """[(rule_id, label, compiled_pattern), ...] for hard triggers with regex."""
    global _compiled_regex_cache
    if _compiled_regex_cache is not None:
        return _compiled_regex_cache

    out: List[Tuple[str, str, "re.Pattern[str]"]] = []
    for trigger in hard_triggers():
        regex_str = trigger.get("regex")
        if not regex_str:
            continue
        try:
            pattern = re.compile(regex_str, re.IGNORECASE | re.UNICODE)
        except re.error:
            # Malformed regex in rules.json — skip silently. Keyword
            # fallback in deterministic.py still covers the trigger.
            continue
        out.append((trigger.get("id", ""), trigger.get("label", ""), pattern))

    _compiled_regex_cache = out
    return out


def reset_cache() -> None:
    """Drop both caches. Use in tests when rules.json is mutated mid-suite."""
    global _rules_cache, _compiled_regex_cache
    _rules_cache = None
    _compiled_regex_cache = None
