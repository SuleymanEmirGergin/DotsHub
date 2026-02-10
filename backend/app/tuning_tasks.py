"""Tuning task generator — deterministic task creation from session analysis.

Analyzes triage sessions to automatically generate tuning tasks:
  - KEYWORD_MISSING: User text contains tokens not mapped to canonicals
  - SPECIALTY_CONFUSION: Top-2 specialties are very close in score
  - QUESTION_WEAKNESS: Selected question has low effectiveness score

All logic is determin istic and rule-based (no LLM calls).
"""

from __future__ import annotations
from typing import Any, Dict, List
from collections import Counter
import re


def extract_tokens(text: str) -> List[str]:
    """Extract significant tokens from Turkish text."""
    if not text:
        return []
    t = text.lower()
    # Keep Turkish characters
    t = re.sub(r"[^\w\sçğıöşü]", " ", t)
    # Return tokens >= 4 chars
    return [w for w in t.split() if len(w) >= 4]


def build_tuning_tasks_from_session(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate tuning tasks from a session dict (from triage_sessions table).
    
    Returns list of task dicts ready to insert into tuning_tasks table.
    """
    tasks: List[Dict[str, Any]] = []

    sid = session.get("id")
    input_text = session.get("input_text") or ""
    canonicals = set(session.get("user_canonicals_tr") or [])
    why = session.get("why_specialty_tr") or []
    scoring_debug = session.get("specialty_scoring_debug") or {}
    selector_debug = session.get("question_selector_debug") or {}

    # ─── Task 1: Missing keyword / synonym ───
    tokens = extract_tokens(input_text)
    # Find tokens that aren't in any canonical
    missed = []
    for t in tokens:
        # Normalize comparison
        t_norm = t.strip().lower()
        found = False
        for c in canonicals:
            if t_norm in c.lower() or c.lower() in t_norm:
                found = True
                break
        if not found and t_norm not in ["var", "yok", "evet", "hayır", "ve", "ile", "için", "ama", "çok", "gibi", "olan", "oldu", "olur", "bir", "bu", "şu"]:
            missed.append(t)

    if len(missed) >= 2:  # At least 2 missed tokens = significant
        freq = Counter(missed)
        top = freq.most_common(5)
        tasks.append({
            "task_type": "KEYWORD_MISSING",
            "severity": "medium",
            "title": "Missing symptom keywords",
            "description": f"Session text contains tokens not mapped to canonicals: {', '.join([t for t, _ in top])}",
            "payload": {
                "missed_tokens": [[t, c] for t, c in top],
                "existing_canonicals": list(canonicals),
            },
            "session_id": sid,
        })

    # ─── Task 2: Specialty confusion ───
    if isinstance(scoring_debug, dict):
        top1 = scoring_debug.get("top1")
        top2 = scoring_debug.get("top2")
        if top1 and top2:
            gap = float(top1.get("final_score", 0)) - float(top2.get("final_score", 0))
            if gap < 0.15:  # Very close
                tasks.append({
                    "task_type": "SPECIALTY_CONFUSION",
                    "severity": "high",
                    "title": f"Confusion between {top1.get('name_tr')} and {top2.get('name_tr')}",
                    "description": f"Top-2 specialties are very close (gap: {gap:.3f}). Consider adjusting specialty keywords or question ordering.",
                    "payload": {
                        "top1": top1,
                        "top2": top2,
                        "gap": gap,
                    },
                    "session_id": sid,
                })

    # ─── Task 3: Weak question ───
    if isinstance(selector_debug, dict):
        eff = selector_debug.get("eff_0_1")
        canonical = selector_debug.get("canonical") if isinstance(scoring_debug, dict) else None
        
        # Check if this is from session's question_selector_debug or embedded elsewhere
        if eff is not None and float(eff) < 0.35:
            tasks.append({
                "task_type": "QUESTION_WEAKNESS",
                "severity": "low",
                "title": f"Weak question: {canonical or 'unknown'}",
                "description": f"This question has low effectiveness score ({eff:.2f}). Consider demoting or rephrasing.",
                "payload": selector_debug,
                "session_id": sid,
            })

    return tasks
