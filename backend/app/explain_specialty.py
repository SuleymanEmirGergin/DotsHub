""""Neden bu branş?" — deterministic explanation builder.

Generates human-readable bullet points explaining WHY a specialty
was recommended, using only debug data from the scoring pipeline.
No LLM. Pure derivation from:
  - text_hits (which keywords matched)
  - answer_hits (which answers affected score)
  - disease prior (which top diseases map to this specialty)
"""

from __future__ import annotations
from typing import Any, Dict, List


def build_why_specialty_tr(
    *,
    top_specialty_id: str,
    specialty_name_tr: str,
    scoring_debug: Dict[str, Any] | None,
    disease_candidates: List[Dict[str, Any]],
    disease_to_specialty_map: Dict[str, Dict[str, Any]],
    max_lines: int = 6,
) -> List[str]:
    """
    Build explanation lines for the recommended specialty.

    Args:
        top_specialty_id: The winning specialty id
        specialty_name_tr: Turkish display name
        scoring_debug: Debug dict from scoring_v2 (keyed by specialty_id)
        disease_candidates: Top disease candidates with score_0_1
        disease_to_specialty_map: disease_label → {specialty_id, specialty_tr, ...}
        max_lines: Max explanation bullets

    Returns:
        List of Turkish explanation strings.
    """
    lines: List[str] = []

    # A) Rules-based evidence (text/answer hits)
    if scoring_debug and top_specialty_id in scoring_debug:
        d = scoring_debug[top_specialty_id]
        text_hits: Dict[str, float] = d.get("text_hits", {})
        ans_hits: Dict[str, float] = d.get("answer_hits", {})

        # Sort by absolute weight (most impactful first)
        for k, w in sorted(
            text_hits.items(), key=lambda x: abs(float(x[1])), reverse=True
        ):
            lines.append(
                f'Metinden eşleşen belirti: \u201c{k}\u201d (+{float(w):.1f})'
            )

        for k, w in sorted(
            ans_hits.items(), key=lambda x: abs(float(x[1])), reverse=True
        ):
            sign = "+" if float(w) >= 0 else ""
            lines.append(
                f'Cevabın etkisi: \u201c{k}\u201d ({sign}{float(w):.1f})'
            )

    # B) Disease prior evidence
    for c in disease_candidates[:3]:
        dis = c.get("disease_label", "")
        score = float(c.get("score_0_1", 0))
        mapping = disease_to_specialty_map.get(dis)
        if mapping and mapping.get("specialty_id") == top_specialty_id:
            lines.append(
                f"Olası durum: {dis} (%{int(score * 100)}) \u2192 {specialty_name_tr}"
            )

    # Fallback
    if not lines:
        lines.append(
            f"Belirti ve cevaplarına göre en uygun branş: {specialty_name_tr}"
        )

    return lines[:max_lines]
