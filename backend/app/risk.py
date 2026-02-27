"""Deterministic risk stratification helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_TR_TO_ASCII = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "c",
        "Ğ": "g",
        "İ": "i",
        "Ö": "o",
        "Ş": "s",
        "Ü": "u",
    }
)


def _norm_token(value: str) -> str:
    token = str(value or "").strip().lower().translate(_TR_TO_ASCII)
    token = token.replace("-", "_").replace("/", "_").replace(" ", "_")
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_")


def _norm_set(values: List[str]) -> set[str]:
    out: set[str] = set()
    for value in values or []:
        normalized = _norm_token(value)
        if normalized:
            out.add(normalized)
    return out


def _any_in(canonicals: List[str], targets: List[str]) -> bool:
    cset = _norm_set(canonicals)
    tset = _norm_set(targets)
    return bool(cset and tset and (cset & tset))


def compute_risk(
    *,
    extracted_canonicals: List[str],
    confidence_0_1: float,
    same_day: Optional[Dict[str, Any]],
    duration_days: Optional[int],
    profile: Optional[Dict[str, Any]],
    risk_rules: Dict[str, Any],
) -> Dict[str, Any]:
    reasons: List[str] = []
    score = 0.0

    confidence = max(0.0, min(1.0, float(confidence_0_1 or 0.0)))
    rules = risk_rules or {}
    high_cfg = rules.get("high", {}) if isinstance(rules, dict) else {}
    med_cfg = rules.get("medium", {}) if isinstance(rules, dict) else {}

    if confidence < 0.35:
        score += 0.25
        reasons.append("Belirsizlik yuksek (dusuk confidence)")

    same_day_active = bool(same_day)
    if same_day_active and bool(med_cfg.get("same_day_if_true", True)):
        score += 0.35
        reasons.append("Same-day kontrol onerisi aktif")

    if duration_days is not None:
        if duration_days >= 14:
            score += 0.30
            reasons.append("Semptom suresi 2 haftayi gecti")
        elif duration_days >= 7:
            score += 0.20
            reasons.append("Semptom suresi 1 haftayi gecti")
        elif duration_days <= 2:
            score -= 0.05
            reasons.append("Semptom suresi kisa (<=2 gun)")

    if profile:
        age = profile.get("age")
        pregnant = profile.get("pregnant")

        if isinstance(age, int):
            if age <= 2:
                score += 0.25
                reasons.append("Cok kucuk yas (<=2)")
            elif age >= 65:
                score += 0.20
                reasons.append("Ileri yas (>=65)")

        if pregnant is True:
            score += 0.20
            reasons.append("Gebelik durumu (ek dikkat)")

    high_any = high_cfg.get("canonicals_any", []) if isinstance(high_cfg, dict) else []
    med_any = med_cfg.get("canonicals_any", []) if isinstance(med_cfg, dict) else []

    high_hit = bool(high_any) and _any_in(extracted_canonicals, high_any)
    med_hit = bool(med_any) and _any_in(extracted_canonicals, med_any)

    same_day_required = bool(high_cfg.get("same_day_required", False))
    if high_hit and (not same_day_required or same_day_active):
        score += 0.55
        reasons.append("Yuksek risk sinyali iceren belirti(ler)")

    if med_hit:
        score += 0.25
        reasons.append("Orta risk sinyali iceren belirti(ler)")

    min_confidence_fallback = float(high_cfg.get("min_confidence_fallback", 0.25))
    if confidence <= min_confidence_fallback and (high_hit or med_hit):
        score += 0.20
        reasons.append("Dusuk confidence + riskli belirti kombinasyonu")

    if duration_days is not None and duration_days <= 2:
        reasons.append("2 gunden kisa sureli semptom")
    if not same_day_active:
        reasons.append("Same-day zorunlulugu saptanmadi")
    reasons.append("Acil belirti saptanmadi")

    score = max(0.0, min(1.0, score))

    if score >= 0.70:
        level = "HIGH"
    elif score >= 0.40:
        level = "MEDIUM"
    else:
        level = "LOW"

    if level == "HIGH":
        advice = "Bugun bir saglik kurulusuna basvurmaniz onerilir. Semptomlar artarsa beklemeyin."
    elif level == "MEDIUM":
        advice = "Bugun veya en kisa surede kontrol planlamak uygun olabilir. Semptomlar artarsa bugun basvurun."
    else:
        advice = "Semptomlar artarsa, yeni sikayet eklenirse veya 48 saat icinde duzelmezse kontrol onerilir."

    uniq_reasons: List[str] = []
    for reason in reasons:
        if reason not in uniq_reasons:
            uniq_reasons.append(reason)

    return {
        "level": level,
        "score_0_1": round(score, 2),
        "reasons": uniq_reasons[:4],
        "advice": advice,
    }
