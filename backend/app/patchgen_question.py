"""Question weakness patch generator.

Given a QUESTION_WEAKNESS tuning task, generates a structured patch
that can be applied to triage_policy.json to demote or skip a weak question.

A "weak question" is one where the effectiveness score (eff_0_1) is below
the configured threshold (default 0.35). The patch recommends:
  1. Adding the canonical to a 'demoted_questions' block in triage_policy.json
     with a priority_penalty so the question is asked less often.
  2. Optionally flagging the question for manual text review when the score
     is very low (< 0.15), which might indicate a phrasing problem.
"""

from __future__ import annotations
from typing import Any, Dict, List


def build_question_weakness_patch_from_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a question demotion patch from a QUESTION_WEAKNESS task.

    Args:
        task: Task dict from tuning_tasks table.

    Returns:
        Patch dict with format::

            {
                "patch_type": "question_demotion",
                "target_file": "config/triage_policy.json",
                "changes": [
                    {
                        "action": "demote_question",
                        "canonical": "ateş",
                        "priority_penalty": 0.3,
                        "reason": "low_effectiveness",
                        "eff_score": 0.22,
                    }
                ],
                "metadata": {...}
            }
    """
    if task.get("task_type") != "QUESTION_WEAKNESS":
        raise ValueError("Task must be QUESTION_WEAKNESS type")

    payload = task.get("payload") or {}

    # Extract effectiveness data from payload (set by question_selector)
    eff = payload.get("eff_0_1")
    canonical = payload.get("canonical") or payload.get("question_canonical") or "unknown"
    question_text = payload.get("question_tr") or payload.get("question_text") or ""
    asked_count = payload.get("asked_count")
    info_gain = payload.get("info_gain") or payload.get("ig") or 0.0

    if eff is None:
        raise ValueError("Task payload missing 'eff_0_1' effectiveness score")

    eff_float = float(eff)

    changes: List[Dict[str, Any]] = []

    # Determine penalty based on severity
    if eff_float < 0.15:
        # Very weak: high penalty + flag for rephrasing
        priority_penalty = 0.6
        flag_for_rephrase = True
        reason = "very_low_effectiveness"
    elif eff_float < 0.25:
        priority_penalty = 0.45
        flag_for_rephrase = True
        reason = "low_effectiveness"
    else:
        priority_penalty = 0.3
        flag_for_rephrase = False
        reason = "below_threshold_effectiveness"

    change: Dict[str, Any] = {
        "action": "demote_question",
        "canonical": canonical,
        "priority_penalty": priority_penalty,
        "reason": reason,
        "eff_score": eff_float,
        "target_config_key": "demoted_questions",
    }

    if flag_for_rephrase:
        change["flag_for_rephrase"] = True
        if question_text:
            change["current_question_text"] = question_text

    if info_gain:
        change["info_gain"] = float(info_gain)

    changes.append(change)

    return {
        "patch_type": "question_demotion",
        "target_file": "config/triage_policy.json",
        "task_id": task.get("id"),
        "session_id": task.get("session_id"),
        "changes": changes,
        "metadata": {
            "total_changes": len(changes),
            "auto_generated": True,
            "flag_for_rephrase": flag_for_rephrase,
            "apply_instruction": (
                "Add the 'canonical' to 'demoted_questions' dict in triage_policy.json "
                "with 'priority_penalty' value. The question selector will reduce "
                "this question's selection probability proportionally."
            ),
        },
    }
