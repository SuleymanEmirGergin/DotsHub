"""Emergency routing system — deterministic detection of critical medical situations.

Given user text and extracted canonicals, evaluates emergency rules to detect
situations requiring immediate medical attention.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
import json
import re


def norm_text_tr(s: str) -> str:
    """Normalize Turkish text for matching."""
    s = (s or "").strip().lower()
    # punctuation -> space, keep Turkish chars
    s = re.sub(r"[^\w\sçğıöşü]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_list(items: List[str]) -> Set[str]:
    """Normalize list of strings to set."""
    return set(norm_text_tr(x) for x in (items or []) if norm_text_tr(x))


def contains_any(text: str, phrases: List[str]) -> bool:
    """Check if text contains any of the phrases."""
    if not phrases:
        return False
    t = text
    for p in phrases:
        pn = norm_text_tr(p)
        if pn and pn in t:
            return True
    return False


def contains_all(text: str, phrases: List[str]) -> bool:
    """Check if text contains all of the phrases."""
    if not phrases:
        return False
    t = text
    for p in phrases:
        pn = norm_text_tr(p)
        if pn and pn not in t:
            return False
    return True


def canon_any(canonicals: Set[str], wanted: List[str]) -> bool:
    """Check if any wanted canonical is present in canonicals set."""
    if not wanted:
        return False
    wn = norm_list(wanted)
    return len(canonicals.intersection(wn)) > 0


def group_match(text: str, canonicals: Set[str], group: Dict[str, Any]) -> bool:
    """Check if group conditions match.
    
    Group can contain keyword_any, keyword_all, canonical_any.
    """
    if "keyword_any" in group and contains_any(text, group["keyword_any"]):
        return True
    if "keyword_all" in group and contains_all(text, group["keyword_all"]):
        return True
    if "canonical_any" in group and canon_any(canonicals, group["canonical_any"]):
        return True
    return False


@dataclass
class EmergencyMatch:
    """Matched emergency rule with details."""
    rule_id: str
    severity: int
    title_tr: str
    message_tr: str
    recommendation_tr: str
    matched_on: Dict[str, Any]


def load_emergency_rules(path: str) -> Dict[str, Any]:
    """Load emergency rules from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_emergency(
    *,
    user_text: str,
    canonicals_tr: List[str],
    rules_cfg: Dict[str, Any]
) -> Optional[EmergencyMatch]:
    """Evaluate emergency rules against user input.
    
    Args:
        user_text: Raw user input text
        canonicals_tr: List of extracted canonical symptoms
        rules_cfg: Emergency rules configuration
        
    Returns:
        EmergencyMatch if any rule triggers, else None
    """
    t = norm_text_tr(user_text)
    cset = norm_list(canonicals_tr)

    global_cfg = rules_cfg.get("global", {})
    min_sev = int(global_cfg.get("min_severity_to_trigger", 2))

    best: Optional[EmergencyMatch] = None

    for r in rules_cfg.get("rules", []):
        sev = int(r.get("severity", 1))
        if sev < min_sev:
            continue

        kw_any = r.get("keyword_any", [])
        kw_all = r.get("keyword_all", [])
        can_any_list = r.get("canonical_any", [])
        require_any_group = r.get("require_any_group", [])

        hit = False
        hit_reasons = {}

        # Base checks
        if kw_all and contains_all(t, kw_all):
            hit = True
            hit_reasons["keyword_all"] = kw_all

        if not hit and kw_any and contains_any(t, kw_any):
            hit = True
            hit_reasons["keyword_any"] = kw_any

        if not hit and can_any_list and canon_any(cset, can_any_list):
            hit = True
            hit_reasons["canonical_any"] = can_any_list

        # Additional gating: at least one group must match
        if hit and require_any_group:
            ok = any(group_match(t, cset, g) for g in require_any_group)
            if not ok:
                hit = False
            else:
                hit_reasons["require_any_group"] = require_any_group

        if hit:
            m = EmergencyMatch(
                rule_id=str(r.get("id")),
                severity=sev,
                title_tr=str(r.get("title_tr", "Acil durum şüphesi")),
                message_tr=str(r.get("message_tr", "")),
                recommendation_tr=str(r.get("recommendation_tr", "112 / Acil Servis")),
                matched_on={
                    "user_text_norm": t,
                    "canonicals_norm": sorted(list(cset)),
                    "reasons": hit_reasons
                }
            )
            # Pick highest severity; tie-breaker by rule_id for determinism
            if (best is None) or (m.severity > best.severity) or (m.severity == best.severity and m.rule_id < best.rule_id):
                best = m

    return best
