"""Discriminative question selector v3 — effectiveness-weighted, adaptive ordering.

Selection logic:
  1. Pool = union of top diseases' TR canonical symptoms
  2. Filter: must exist in question_bank, not already answered/asked
  3. Score each candidate with weighted formula:
     - Discrimination score (0.55): |presence_ratio - 0.5|
     - Effectiveness score (0.35): from question_effectiveness report
     - Balance score (0.10): yes/no answer distribution closeness to 50%
     - Coverage penalty: demote over-asked low-effectiveness questions
  4. Pick best (tie-break: alphabetical for determinism)

Improvements over v2:
  - Uses historical effectiveness data to prioritize impactful questions
  - Penalizes questions that are asked frequently but have low effectiveness
  - Returns debug info for analytics/tuning
"""

from __future__ import annotations
from typing import Any, Dict, List, Set, Tuple


def select_discriminative_question_v3(
    *,
    top_diseases: List[str],
    disease_to_canonicals_tr: Dict[str, Set[str]],
    asked_canonicals: List[str],
    answers: Dict[str, str],
    question_bank: Dict[str, Any],
    question_effectiveness_map: Dict[str, Any],
    avoid_canonicals: Set[str] | None = None,
) -> Dict[str, Any]:
    """
    Effectiveness-weighted question selection.
    
    Args:
        top_diseases: List of top disease candidates
        disease_to_canonicals_tr: disease_label -> set of TR canonicals
        asked_canonicals: Already asked canonical symptoms
        answers: Already answered { canonical: value }
        question_bank: Full question bank with questions_by_canonical
        question_effectiveness_map: canonical -> effectiveness row from report
        avoid_canonicals: Canonicals to skip
        
    Returns:
        Question dict with canonical, question_tr, answer_type, selector_debug
    """
    avoid_canonicals = avoid_canonicals or set()
    answered = set([str(k).strip().lower() for k in (answers or {}).keys()])
    asked = set([str(c).strip().lower() for c in (asked_canonicals or [])])

    # Build candidate pool from top diseases
    pool: Set[str] = set()
    for d in top_diseases:
        pool |= set([c.lower() for c in disease_to_canonicals_tr.get(d, set())])

    # Must exist in question bank
    questions_by_canonical = question_bank.get("questions_by_canonical", {})
    if not questions_by_canonical:
        # Fall back to building from questions array
        questions_by_canonical = {}
        for q in question_bank.get("questions", []):
            c = q.get("canonical_symptom", "").strip().lower()
            if c:
                questions_by_canonical[c] = q
    
    bank_canonicals = set([k.lower() for k in questions_by_canonical.keys()])
    pool = pool & bank_canonicals
    
    # Remove answered / asked / avoid
    pool = {c for c in pool if c not in answered and c not in asked and c not in avoid_canonicals}

    if not pool:
        return {
            "canonical": None,
            "question_tr": None,
            "answer_type": None,
            "question_id": None,
            "choices_tr": None,
            "why_asking_tr": None,
            "selector_debug": None,
        }

    n = max(1, len(top_diseases))

    scored: List[Tuple[float, str, Dict[str, Any]]] = []

    for c in sorted(pool):  # sort for determinism
        # Count presence in top diseases
        present = 0
        for d in top_diseases:
            if c in set([x.lower() for x in disease_to_canonicals_tr.get(d, set())]):
                present += 1
        p = present / n
        
        # Discrimination score: further from 0.5 = more discriminative
        disc = abs(p - 0.5)  # Range: 0..0.5

        # Get effectiveness data (with defaults)
        qe = question_effectiveness_map.get(c, {})
        eff = float(qe.get("effectiveness_0_1", 0.50))  # Default: neutral
        balance = float(qe.get("balance_0_1", 0.50)) if qe else 0.50

        # Coverage penalty: demote over-asked low-effectiveness questions
        asked_count = float(qe.get("asked_count", 0)) if qe else 0.0
        coverage_penalty = 0.0
        if asked_count >= 80 and eff < 0.35:
            coverage_penalty = 0.10  # Significant penalty

        # Normalize discrimination to 0..1 (disc is 0..0.5)
        disc_n = disc * 2.0

        # Weighted final score
        final = (0.55 * disc_n) + (0.35 * eff) + (0.10 * balance) - coverage_penalty

        debug = {
            "p_present": round(p, 3),
            "disc_0_1": round(disc_n, 3),
            "eff_0_1": round(eff, 3),
            "balance_0_1": round(balance, 3),
            "coverage_penalty": coverage_penalty,
            "final": round(final, 4),
        }

        scored.append((final, c, debug))

    # Sort by final score descending, then alphabetically for tie-break
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_score, best_canonical, best_debug = scored[0]

    # Get question from bank
    q = questions_by_canonical.get(best_canonical, {})
    
    return {
        "question_id": q.get("question_id", f"q_{best_canonical}"),
        "canonical": best_canonical,
        "question_tr": q.get("question_tr"),
        "answer_type": q.get("answer_type", "yes_no"),
        "choices_tr": q.get("choices_tr"),
        "why_asking_tr": q.get("why_asking_tr"),
        "selector_debug": best_debug,  # For admin/analytics
    }
