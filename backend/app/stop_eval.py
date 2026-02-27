"""Stop rules evaluator — JSON-driven, deterministic.

Reads thresholds from stop_rules.json and decides whether to stop asking
questions and produce a RESULT envelope.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple


def should_stop(
    turn_index: int,
    max_questions: int,
    top_disease_score: float,
    specialty_gap: float,
    no_question_available: bool,
    stop_rules: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Returns (should_stop, reason_id).
    reason_id is None when should_stop is False.
    """
    # Hard stop: max questions reached
    if turn_index >= max_questions:
        return True, "MAX_QUESTIONS_REACHED"

    conf_rules = stop_rules.get("confidence_rules", {})
    hi = float(conf_rules.get("high_confidence_disease_score", 0.45))
    gap_min = float(conf_rules.get("min_specialty_score_gap", 2.0))

    if top_disease_score >= hi:
        return True, "HIGH_CONFIDENCE_SINGLE_DISEASE"

    if specialty_gap >= gap_min:
        return True, "CLEAR_SPECIALTY_WINNER"

    if no_question_available:
        return True, "NO_MORE_DISCRIMINATIVE_QUESTIONS"

    return False, None
