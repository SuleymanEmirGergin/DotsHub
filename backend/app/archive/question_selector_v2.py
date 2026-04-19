"""Discriminative question selector v2 — answers-aware, deterministic.

Selection logic:
  1. Pool = union of top diseases' TR canonical symptoms
  2. Filter: must exist in question_bank, not already answered/asked
  3. Score: discriminative score = |presence_ratio - 0.5|
     (0.5 = appears in half the top diseases = maximally ambiguous)
     Higher = more discriminative (present in few or many top diseases)
  4. Pick best (tie-break: alphabetical for determinism)

Adapted to actual question bank format:
  {
    "questions": [
      { "canonical_symptom": "baş ağrısı", "question_tr": "...", "answer_type": "yes_no" }
    ]
  }
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple


def select_discriminative_question_v2(
    *,
    top_diseases: List[str],
    disease_to_canonicals_tr: Dict[str, Set[str]],
    asked_canonicals: List[str],
    answers: Dict[str, str],
    questions_by_canonical: Dict[str, Dict[str, Any]],
    avoid_canonicals: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Deterministic question selection.
    Returns question dict or empty-ish dict if no question available.
    """
    avoid = avoid_canonicals or set()
    answered = {k.strip().lower() for k in (answers or {})}
    asked = {c.strip().lower() for c in (asked_canonicals or [])}

    # Candidate pool = union of top diseases' symptoms
    pool: Set[str] = set()
    for d in top_diseases:
        syms = disease_to_canonicals_tr.get(d, set())
        pool |= {c.lower() for c in syms}

    # Must exist in question bank
    bank_canonicals = set(questions_by_canonical.keys())
    pool = pool & bank_canonicals

    # Remove answered / asked / avoid
    pool = {c for c in pool if c not in answered and c not in asked and c not in avoid}

    if not pool:
        return {
            "canonical": None,
            "question_tr": None,
            "answer_type": None,
            "question_id": None,
            "choices_tr": None,
            "why_asking_tr": None,
        }

    # Compute discriminative score for each candidate
    n = max(1, len(top_diseases))
    scored: List[Tuple[float, str]] = []

    for c in sorted(pool):  # sort for determinism
        present = 0
        for d in top_diseases:
            d_syms = {x.lower() for x in disease_to_canonicals_tr.get(d, set())}
            if c in d_syms:
                present += 1
        p = present / n
        discr = abs(p - 0.5)  # further from 0.5 = more discriminative
        scored.append((discr, c))

    # Pick best (highest discriminative score, tie-break by name desc for stability)
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_canonical = scored[0][1]

    q = questions_by_canonical.get(best_canonical, {})
    return {
        "question_id": q.get("question_id", f"q_{best_canonical}"),
        "canonical": best_canonical,
        "question_tr": q.get("question_tr"),
        "answer_type": q.get("answer_type", "yes_no"),
        "choices_tr": q.get("choices_tr"),
        "why_asking_tr": q.get("why_asking_tr"),
    }
