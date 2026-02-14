"""
Serbest metin cevaplarının yapılandırılması: süre, şiddet, zamanlama.

- Süre: "3 gündür", "1 haftadır" -> duration_days
- Şiddet: "çok kötü", "hafif", "7" -> severity_0_10 (1-10)
- Zamanlama: "sabah kalkınca", "gece" -> timing (sabah/akşam/gece/gündüz)
"""

import re
from typing import Any, Dict, List, Optional

from app.duration_parse import extract_duration_days


# Canonicals that expect duration (free-text answers parsed to days)
DURATION_CANONICALS = {
    "öksürük süresi",
    "baş ağrısı süresi",
    "karın ağrısı süresi",
    "ateş süresi",
    "ishal süresi",
    "boğaz ağrısı süresi",
    "göğüs ağrısı süresi",
}

# Canonicals that expect severity (1-10 or verbal)
SEVERITY_CANONICALS = {
    "ağrı şiddeti",
}

# Canonicals that can have timing (sabah/akşam/gece/gündüz)
TIMING_CANONICALS = {
    "öksürük gece artışı",
    "baş ağrısı sabah artışı",
    "öksürük süresi",
    "baş ağrısı süresi",
}

# Verbal severity -> 1-10 (approximate)
SEVERITY_MAP = [
    ("çok şiddetli", "çok kötü", "dayanılmaz", "10", "10/10"),  # 9-10
    ("şiddetli", "kötü", "fena", "8", "9"),                     # 8-9
    ("orta", "oldukça", "7", "6", "5"),                         # 5-7
    ("hafif", "az", "biraz", "3", "4", "2", "1"),              # 1-4
]
SEVERITY_VALUES = [9, 8, 6, 2]  # representative value per group

TIMING_KEYWORDS = [
    ("sabah", "sabah", "kalkınca", "kalktığımda", "erkenden"),
    ("akşam", "akşam", "akşamları", "akşamleyin"),
    ("gece", "gece", "geceleri", "yatarken", "uyurken", "geceleyin"),
    ("gündüz", "gündüz", "gün içinde", "gün boyu"),
]


def parse_duration(text: str) -> Optional[int]:
    """Parse duration in days from Turkish text. Wrapper around extract_duration_days."""
    return extract_duration_days(text or "")


def parse_severity(text: str) -> Optional[float]:
    """
    Parse severity from Turkish text to 1-10 scale.
    - Numeric "7" or "7/10" -> 7
    - Verbal "hafif" -> ~2, "orta" -> ~6, "şiddetli" -> ~8
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip().lower()

    # Numeric: 7, 7/10, 8 out of 10
    m = re.search(r"(\d{1,2})\s*(/|out of)?\s*10?", t)
    if m:
        try:
            n = int(m.group(1))
            if 0 <= n <= 10:
                return float(n)
        except (ValueError, IndexError):
            pass
    m = re.search(r"^(\d)[\s\-]*(?:/|üzerinden)?\s*10?$", t)
    if m:
        try:
            n = int(m.group(1))
            if 0 <= n <= 10:
                return float(n)
        except (ValueError, IndexError):
            pass

    for i, keywords in enumerate(SEVERITY_MAP):
        for kw in keywords:
            if kw in t:
                return float(SEVERITY_VALUES[i])
    return None


def parse_timing(text: str) -> Optional[str]:
    """
    Parse timing from Turkish text to one of: sabah, akşam, gece, gündüz.
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip().lower()

    for value, *keywords in TIMING_KEYWORDS:
        for kw in keywords:
            if kw in t:
                return value
    return None


def parse_free_text_answer(canonical: str, raw_value: str) -> Dict[str, Any]:
    """
    Given a canonical symptom (from question) and the user's raw answer,
    return structured fields: duration_days, severity_0_10, timing.

    Only includes keys that were successfully parsed.
    """
    if not canonical or not raw_value:
        return {}
    canonical = (canonical or "").strip()
    raw = (raw_value or "").strip()
    if not raw:
        return {}

    out: Dict[str, Any] = {}

    if canonical in DURATION_CANONICALS:
        days = parse_duration(raw)
        if days is not None:
            out["duration_days"] = days

    if canonical in SEVERITY_CANONICALS:
        sev = parse_severity(raw)
        if sev is not None:
            out["severity_0_10"] = sev

    if canonical in TIMING_CANONICALS:
        timing = parse_timing(raw)
        if timing:
            out["timing"] = timing

    return out


def parsed_to_symptom_item(canonical: str, parsed: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Convert parsed answer to a minimal symptom-like dict for stop condition:
    { "name_tr": canonical, "duration_tr": "3 gün"?, "severity_0_10": 7? }.
    Used to merge into structured_symptoms so onset_or_duration_present and severity_estimated get set.
    """
    if not parsed:
        return None
    item: Dict[str, Any] = {"name_tr": canonical}
    if "duration_days" in parsed:
        item["duration_tr"] = f"{parsed['duration_days']} gün"
    if "severity_0_10" in parsed:
        item["severity_0_10"] = parsed["severity_0_10"]
    if len(item) <= 1:
        return None
    return item
