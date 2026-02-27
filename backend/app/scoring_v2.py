"""Deterministic specialty scoring v2 — text hits + answer boosts + disease prior.

3 signal sources:
  A) Free-text keyword hits (from specialty_keywords_tr.json)
  B) Structured answer boosts (YES → boost, NO → penalty)
  C) Negative keyword penalty

Adapted to the existing specialty_keywords_tr.json format:
  {
    "specialties": [
      {
        "id": "neurology",
        "specialty_tr": "Nöroloji",
        "keywords_tr": ["baş ağrısı", ...],
        "negative_keywords_tr": [...]
      }
    ],
    "scoring": {
      "keyword_match_points": 3,
      "phrase_match_points": 5,
      "negative_keyword_penalty": -4
    }
  }

Plus v2 answer_boosts: loaded from specialty_keywords if present, or
inferred from keyword presence.
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.canonical_extract import extract_canonicals_tr, normalize_text_tr


def score_specialties_deterministic_v2(
    text_tr: str,
    answers: Dict[str, str],
    synonyms_json: Dict[str, Any],
    specialty_keywords_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns:
      {
        "scores": { specialty_id: float, ... },
        "ranked": [ { "id": ..., "specialty_tr": ..., "final_score": ... }, ... ],
        "debug": { specialty_id: { "text_hits": {...}, "answer_hits": {...}, "negatives": {...} } }
      }
    """
    # Extract canonicals from text
    canonicals = extract_canonicals_tr(
        text_tr=text_tr,
        answers={},  # answers handled separately below
        synonyms_json=synonyms_json,
    )
    canonical_set = set(canonicals)
    text_norm = normalize_text_tr(text_tr)

    scoring_cfg = specialty_keywords_json.get("scoring", {})
    kw_points = float(scoring_cfg.get("keyword_match_points", 3))
    neg_penalty = float(scoring_cfg.get("negative_keyword_penalty", -4))

    scores: Dict[str, float] = defaultdict(float)
    debug: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"text_hits": {}, "answer_hits": {}, "negatives": {}}
    )

    for spec in specialty_keywords_json.get("specialties", []):
        sid = spec.get("id", "")
        if not sid:
            continue

        # A) Text keyword hits
        for kw in spec.get("keywords_tr", []):
            kw_norm = normalize_text_tr(kw)
            if kw_norm in canonical_set or kw_norm in text_norm:
                scores[sid] += kw_points
                debug[sid]["text_hits"][kw] = kw_points

        # B) Negative keywords
        for nkw in spec.get("negative_keywords_tr", []):
            nkw_norm = normalize_text_tr(nkw)
            if nkw_norm in canonical_set or nkw_norm in text_norm:
                scores[sid] += neg_penalty
                debug[sid]["negatives"][nkw] = neg_penalty

        # C) Answer boosts (v2 extension)
        # If specialty has explicit answer_boosts, use them
        answer_boosts = spec.get("answer_boosts", {})
        if answer_boosts:
            for q_canonical, rule in answer_boosts.items():
                q_norm = normalize_text_tr(q_canonical)
                if q_norm in answers:
                    val = answers[q_norm].lower().strip()
                    delta = rule.get(val)
                    if delta is not None:
                        scores[sid] += float(delta)
                        debug[sid]["answer_hits"][f"{q_canonical}:{val}"] = float(delta)
        else:
            # Fallback: if answer canonical matches a keyword → boost/penalty
            for kw in spec.get("keywords_tr", []):
                kw_norm = normalize_text_tr(kw)
                if kw_norm in answers:
                    val = answers[kw_norm].lower().strip()
                    if val == "yes":
                        delta = kw_points * 0.7  # slightly less than text hit
                        scores[sid] += delta
                        debug[sid]["answer_hits"][f"{kw}:yes"] = delta
                    elif val == "no":
                        delta = -kw_points * 0.3
                        scores[sid] += delta
                        debug[sid]["answer_hits"][f"{kw}:no"] = delta

    # Build ranked list
    ranked: List[Dict[str, Any]] = []
    for spec in specialty_keywords_json.get("specialties", []):
        sid = spec.get("id", "")
        if sid:
            ranked.append({
                "id": sid,
                "specialty_tr": spec.get("specialty_tr", sid),
                "final_score": round(scores.get(sid, 0.0), 2),
            })
    ranked.sort(key=lambda x: x["final_score"], reverse=True)

    return {
        "scores": dict(scores),
        "ranked": ranked,
        "debug": dict(debug),
    }


def compute_specialty_prior(
    candidates: List[Dict[str, Any]],
    disease_to_specialty_list: List[Dict[str, Any]],
    fallback_id: str = "internal_gi",
    fallback_tr: str = "Dahiliye (gerekirse Gastroenteroloji)",
) -> Dict[str, float]:
    """
    Compute specialty prior from disease candidates.
    Each candidate's score_0_1 contributes to the specialty it maps to.
    """
    # Build lookup: disease_label → specialty entry
    d2s: Dict[str, Dict[str, Any]] = {}
    for entry in disease_to_specialty_list:
        dl = entry.get("disease_label", "")
        if dl:
            d2s[dl] = entry

    prior: Dict[str, float] = defaultdict(float)
    for c in candidates:
        dl = c.get("disease_label", "")
        score = float(c.get("score_0_1", 0.0))
        mapping = d2s.get(dl)
        if mapping:
            sid = mapping.get("specialty_id", fallback_id)
            conf = float(mapping.get("confidence", 0.8))
            prior[sid] += score * conf
        else:
            prior[fallback_id] += score * 0.3

    return dict(prior)


def merge_final_specialty_scores(
    rules_scores: Dict[str, float],
    prior_scores: Dict[str, float],
    rules_weight: float = 0.6,
    prior_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Merge rules-based scores with disease-prior scores.
    Returns sorted list of { id, final_score }.
    """
    all_ids = set(list(rules_scores.keys()) + list(prior_scores.keys()))
    merged: List[Tuple[str, float]] = []
    for sid in all_ids:
        r = rules_scores.get(sid, 0.0)
        p = prior_scores.get(sid, 0.0)
        final = (r * rules_weight) + (p * prior_weight)
        merged.append((sid, round(final, 3)))

    merged.sort(key=lambda x: x[1], reverse=True)
    return [{"id": sid, "final_score": score} for sid, score in merged]
