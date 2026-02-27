"""Result explainability helpers for deterministic orchestration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_explanation_trace(
    *,
    extracted_canonicals: List[str],
    confidence_0_1: float,
    stop_reason: Optional[str],
    same_day: Optional[Dict[str, Any]],
    duration_days: Optional[int],
    profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    summary: List[str] = []

    if extracted_canonicals:
        top = ", ".join(extracted_canonicals[:6])
        summary.append(f"Tespit edilen belirtiler: {top}")

    summary.append(f"Guven skoru: {round(float(confidence_0_1 or 0.0), 2)}")

    if stop_reason:
        summary.append(f"Durdurma nedeni: {stop_reason}")

    if same_day:
        summary.append("Same-day kontrol onerisi aktif")

    if duration_days is not None:
        summary.append(f"Semptom suresi: {duration_days} gun")

    if profile:
        parts: List[str] = []
        age = profile.get("age")
        preg = profile.get("pregnant")
        if isinstance(age, int):
            parts.append(f"yas {age}")
        if preg is True:
            parts.append("gebelik")
        if parts:
            summary.append(f"Profil: {', '.join(parts)}")

    return {"summary": summary}
