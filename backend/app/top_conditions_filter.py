"""A9 confidence gate + disease label override — pure-function module.

This module implements two Stream A safeguards as **standalone pure functions**
that can be called from the result-assembly path without modifying the
existing orchestrator code in place.

Behaviors:
  1. **Confidence gate**: When ``confidence < MIN_CONFIDENCE_FOR_CONDITIONS``,
     ``apply_top_conditions_gate`` returns an empty list — the UI should show
     only the recommended specialty, suppressing fragile differential diagnoses
     (e.g., "Paralysis (brain hemorrhage)") from leaking into the result.
  2. **Label override**: ``apply_label_overrides`` rewrites Kaggle-origin
     English disease labels to Turkish display labels, preserving the original
     ``disease_label`` as a ``_source_label`` field for traceability.

Both functions are idempotent and side-effect free. They are designed to be
invoked from ``backend/app/agents/orchestrator._build_result_payload`` and
``backend/app/orchestrator_v5.build_result`` immediately before the
``top_conditions`` list is written into the response envelope.

Emergency envelope bypass:
  The gate should NOT be applied to EMERGENCY envelopes — caller is responsible
  for skipping ``apply_top_conditions_gate`` when ``envelope.type == "EMERGENCY"``.
  Emergencies carry their own deterministic rule-based reasoning and must
  always surface to the UI regardless of model confidence.

Integration (apply in ``_build_result_payload`` near line 722):

    from backend.app.top_conditions_filter import (
        apply_top_conditions_gate,
        apply_label_overrides,
        load_label_overrides,
    )

    raw_top = [
        {"disease_label": d["disease_label"], "score_0_1": round(d["score_0_1"], 2)}
        for d in state.disease_candidates[:3]
    ]
    gated_top = apply_top_conditions_gate(raw_top, state.confidence)
    overrides = load_label_overrides()
    top_conditions = apply_label_overrides(gated_top, overrides)

See ``docs/medical/a9_integration.md`` for the full integration diff.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── Public constants ────────────────────────────────────────────────────────
#
# Threshold below which the ``top_conditions`` list is emptied.
# Rationale (see ``docs/medical/coverage_audit.md §6``): below 0.35, differential
# diagnoses from the Kaggle-origin matrix are noisier than signal and risk
# presenting "Brain hemorrhage" / "Heart attack" to the user on thin evidence.
# Matches the existing risk-booster threshold in ``backend/app/risk.py:66``.
MIN_CONFIDENCE_FOR_CONDITIONS: float = 0.35


# ── Pure helpers ────────────────────────────────────────────────────────────

def apply_top_conditions_gate(
    top_conditions: List[Dict[str, Any]],
    confidence: Optional[float],
    threshold: float = MIN_CONFIDENCE_FOR_CONDITIONS,
) -> List[Dict[str, Any]]:
    """Return ``top_conditions`` unchanged if confidence ≥ threshold, else ``[]``.

    Args:
        top_conditions: List of {disease_label, score_0_1, ...} dicts.
        confidence: Session confidence in [0, 1]. If ``None`` the gate is bypassed
            (backwards-compatible — callers that haven't wired confidence yet
            keep current behavior).
        threshold: Minimum confidence required to surface conditions. Defaults
            to ``MIN_CONFIDENCE_FOR_CONDITIONS``.

    Returns:
        Empty list when ``confidence`` is below ``threshold``, otherwise the
        input list unmodified (same object reference — caller may mutate).
    """
    if confidence is None:
        return top_conditions
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        log.warning("apply_top_conditions_gate: unparseable confidence=%r — bypassing gate", confidence)
        return top_conditions
    if c < threshold:
        log.info(
            "A9 gate: suppressing %d top_conditions (confidence=%.3f < %.3f)",
            len(top_conditions), c, threshold,
        )
        return []
    return top_conditions


def apply_label_overrides(
    top_conditions: List[Dict[str, Any]],
    overrides: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Rewrite ``disease_label`` on each condition using ``overrides`` map.

    The original label is preserved under ``_source_label`` for audit/debug
    (analytics dashboards key on the source label, not the display label).

    Args:
        top_conditions: List of condition dicts, each with a ``disease_label``.
        overrides: ``{source_label: tr_display_label}``.

    Returns:
        New list with rewritten labels. Input not mutated.
    """
    if not overrides:
        return list(top_conditions)
    out: List[Dict[str, Any]] = []
    for c in top_conditions:
        src = c.get("disease_label", "")
        tr_label = overrides.get(src)
        if tr_label:
            new_c = dict(c)
            new_c["disease_label"] = tr_label
            new_c["_source_label"] = src
            out.append(new_c)
        else:
            out.append(dict(c))
    return out


# ── Data loader ─────────────────────────────────────────────────────────────

_OVERRIDES_CACHE: Optional[Dict[str, str]] = None


def load_label_overrides(
    path: Optional[Path] = None,
    *,
    force_reload: bool = False,
) -> Dict[str, str]:
    """Load (and cache) the disease-label override map.

    The map lives at ``backend/app/data/disease_label_overrides.json``. The
    file structure is ``{"overrides": {source: tr_label}}``. A missing file
    returns an empty dict so this module is safe to call in environments
    without the override asset.

    Args:
        path: Optional explicit path for testing.
        force_reload: Bypass the module-level cache.

    Returns:
        ``{source_label: tr_display_label}`` dict.
    """
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None and not force_reload and path is None:
        return _OVERRIDES_CACHE

    target = path or (Path(__file__).parent / "data" / "disease_label_overrides.json")
    try:
        with open(target, "r", encoding="utf-8") as f:
            raw = json.load(f)
        overrides = raw.get("overrides", {})
        if not isinstance(overrides, dict):
            log.warning("disease_label_overrides.json: 'overrides' is not a dict — ignoring")
            overrides = {}
    except FileNotFoundError:
        log.info("disease_label_overrides.json not found at %s — overrides disabled", target)
        overrides = {}
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load disease_label_overrides.json: %s", e)
        overrides = {}

    if path is None:
        _OVERRIDES_CACHE = overrides
    return overrides


def clear_cache() -> None:
    """Test hook — reset the module-level overrides cache."""
    global _OVERRIDES_CACHE
    _OVERRIDES_CACHE = None


# ── Convenience wrapper ─────────────────────────────────────────────────────

def filter_top_conditions(
    raw_top_conditions: List[Dict[str, Any]],
    confidence: Optional[float],
    *,
    envelope_type: str = "RESULT",
    threshold: float = MIN_CONFIDENCE_FOR_CONDITIONS,
    overrides: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """One-shot: gate → override pipeline, with EMERGENCY bypass.

    This is the single public entry point for call sites that want the full
    behavior in one call.

    Args:
        raw_top_conditions: Raw list from ``state.disease_candidates[:3]``.
        confidence: Session confidence in [0, 1].
        envelope_type: If ``"EMERGENCY"``, the gate is skipped (emergencies
            always surface).
        threshold: Override the default confidence threshold.
        overrides: Override map. If ``None``, loads from the JSON asset.

    Returns:
        Final ``top_conditions`` list for the envelope payload.
    """
    if envelope_type == "EMERGENCY":
        gated = raw_top_conditions
    else:
        gated = apply_top_conditions_gate(raw_top_conditions, confidence, threshold=threshold)

    if overrides is None:
        overrides = load_label_overrides()

    return apply_label_overrides(gated, overrides)
