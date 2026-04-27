"""Fit-to-travel rule evaluator.

Reads ``app/data/fit_to_travel_rules.json`` and applies it against a
``HealthTourismProfile`` for a given procedure. Returns a list of
warnings (and at most one ``block``) — the route handler decides what
to do with them:

  - any ``block`` → return ERROR/EMERGENCY-style envelope, no quote.
  - only ``warn`` → continue to quote, attach warnings to payload.

Why mirror the emergency-rules pattern
    The same shape (id + severity + reason + recommendation) means
    any clinical reviewer who knows the triage rules can read these
    too. The predicate is structured (boolean trigger keys) instead
    of free-text keywords because the input is a typed profile, not
    user prose.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List

from app.models.schemas import FitToTravelWarning, HealthTourismProfile

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "fit_to_travel_rules.json"

# Mirror of the boolean fields on HealthTourismProfile that rules can
# trigger on. Kept as a separate constant so a typo in
# fit_to_travel_rules.json (e.g. "active_canser") fails loudly at
# import-time validation rather than silently no-op'ing at runtime.
KNOWN_TRIGGER_KEYS: frozenset[str] = frozenset({
    "recent_mi",
    "unstable_angina",
    "decompensated_heart_failure",
    "uncontrolled_hypertension",
    "uncontrolled_diabetes",
    "active_cancer",
    "active_chemo",
    "pregnancy",
    "breastfeeding",
    "smoker_active",
    "dvt_history",
    "anticoagulant_therapy",
    "bisphosphonate_therapy",
    "active_infection",
    "active_eye_infection",
    "dry_eye_severe",
    "bruxism_severe",
    "uncontrolled_thyroid",
    "severe_copd",
    "dialysis_dependent",
    "bmi_over_35",
    "bmi_over_55",
})


@lru_cache(maxsize=1)
def _load_rules() -> list[dict[str, Any]]:
    with _DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    rules = data.get("rules") or []
    # Validate every trigger key against the known set — surface
    # typos at import time. Same reason curated-fields registry has
    # `test_curated_fields_registry_covers_known_new_keys` in the
    # capability gating tests.
    for rule in rules:
        for key in rule.get("trigger_keys", []):
            if key not in KNOWN_TRIGGER_KEYS:
                raise ValueError(
                    f"fit_to_travel_rules.json: rule '{rule.get('id')}' "
                    f"references unknown trigger_key '{key}'. Add it to "
                    f"KNOWN_TRIGGER_KEYS in services/fit_to_travel.py + "
                    f"to HealthTourismProfile."
                )
    return rules


def _rule_applies_to(rule: dict[str, Any], procedure_id: str) -> bool:
    applies = rule.get("applies_to_procedures")
    if applies == "*":
        return True
    if isinstance(applies, list):
        return procedure_id in applies
    # Defensive: malformed → don't apply (rule writer error).
    return False


def _profile_triggers(profile: HealthTourismProfile, rule: dict[str, Any]) -> bool:
    """Returns True if any trigger_key on the rule is True on the profile.

    OR semantics across multiple trigger keys is intentional — most
    rules list synonymous flags (e.g. ``active_cancer`` and
    ``active_chemo``) so any one being set is enough.
    """
    profile_dict = profile.model_dump()
    for key in rule.get("trigger_keys", []):
        if profile_dict.get(key) is True:
            return True
    return False


def _localised_text(rule: dict[str, Any], field: str, locale: str | None) -> str:
    """Pull ``rule[field][short-locale]`` with TR/EN fallback."""
    block = rule.get(field, {})
    if not isinstance(block, dict):
        return ""
    short = (locale or "tr").split("-")[0].split("_")[0].lower()
    return block.get(short) or block.get("tr") or block.get("en") or ""


def evaluate(
    profile: HealthTourismProfile,
    procedure_id: str,
    locale: str | None = None,
) -> List[FitToTravelWarning]:
    """Return every fit-to-travel warning that applies.

    Output is ordered: ``block`` rules first (so callers checking the
    first element catch the hard stop), then ``warn`` rules in JSON
    file order.
    """
    out: list[FitToTravelWarning] = []
    for rule in _load_rules():
        if not _rule_applies_to(rule, procedure_id):
            continue
        if not _profile_triggers(profile, rule):
            continue
        out.append(
            FitToTravelWarning(
                rule_id=rule["id"],
                severity=rule["severity"],
                reason_tr=_localised_text(rule, "reason", locale),
                recommendation_tr=_localised_text(rule, "recommendation", locale),
            )
        )
    out.sort(key=lambda w: 0 if w.severity == "block" else 1)
    return out


def has_block(warnings: Iterable[FitToTravelWarning]) -> bool:
    return any(w.severity == "block" for w in warnings)
