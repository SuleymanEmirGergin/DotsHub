"""Backend-authoritative confidence calculation.

Multi-signal confidence:
  - disease_conf: top1 disease score
  - disease_gap:  top1 - top2 separation
  - specialty_gap: top1 - top2 specialty score gap (normalized)
  - question_factor: how many questions answered vs ideal

All deterministic. Same inputs → same output.
"""

from __future__ import annotations
from typing import Dict, Tuple


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def confidence_label_tr(v: float) -> str:
    if v >= 0.7:
        return "Yüksek"
    if v >= 0.45:
        return "Orta"
    return "Düşük"


def compute_confidence(
    top1_disease: float,
    top2_disease: float,
    top1_spec: float,
    top2_spec: float,
    asked_count: int,
    ideal_questions: int = 4,
) -> Tuple[float, str, str, Dict[str, float]]:
    """
    Returns (confidence_0_1, label_tr, explain_tr, debug_dict).
    """
    disease_conf = top1_disease
    disease_gap = max(0.0, top1_disease - top2_disease)

    specialty_gap = max(0.0, top1_spec - top2_spec)
    specialty_gap_norm = clamp01(specialty_gap / 4.0)

    question_factor = clamp01(asked_count / float(max(1, ideal_questions)))

    conf = clamp01(
        (disease_conf * 0.45)
        + (disease_gap * 0.25)
        + (specialty_gap_norm * 0.20)
        + (question_factor * 0.10)
    )

    label = confidence_label_tr(conf)

    explain = (
        "Olası durumlar arasında net bir ayrım var ve önerilen branş belirgin."
        if label == "Yüksek"
        else "Birden fazla olasılık var. Doktora giderken özeti göstermen iyi olur."
        if label == "Orta"
        else "Belirsizlik yüksek. Semptomlar değişirse değerlendirmeyi yenile."
    )

    debug = {
        "disease_confidence": round(disease_conf, 4),
        "disease_gap": round(disease_gap, 4),
        "specialty_gap_norm": round(specialty_gap_norm, 4),
        "question_factor": round(question_factor, 4),
        "top1_spec": round(top1_spec, 4),
        "top2_spec": round(top2_spec, 4),
    }

    return conf, label, explain, debug
