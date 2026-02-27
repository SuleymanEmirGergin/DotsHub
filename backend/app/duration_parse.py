"""Simple deterministic duration parser for Turkish symptom text."""

from __future__ import annotations

import re
from typing import Optional

# Turkish: gün, gündür, hafta, haftadır, ay, aydır (with optional diacritics)
TR_DAY_PATTERNS = [
    r"(\d+)\s*g[uü]nd[uü]r",   # 2 gündür
    r"(\d+)\s*g[uü]n\s*oldu",
    r"(\d+)\s*g[uü]n\s*dir",
    r"(\d+)\s*g[uü]n\b",       # 2 gün
    r"(\d+)\s*g[uü]nl[uü]k",   # 2 günlük
]
TR_WEEK_PATTERNS = [
    r"(\d+)\s*haftad[iı]r",
    r"(\d+)\s*hafta\s*oldu",
    r"(\d+)\s*hafta\b",
]
TR_MONTH_PATTERNS = [
    r"(\d+)\s*ayd[iı]r",
    r"(\d+)\s*ay\s*oldu",
    r"(\d+)\s*ay\b",
]


def extract_duration_days(text: str) -> Optional[int]:
    """Parse Turkish duration phrases into approximate days.
    E.g. '3 gündür', '1 haftadır', '2 aydır' -> 3, 7, 60.
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip().lower()

    for pat in TR_DAY_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            try:
                days = int(m.group(1))
                if 0 < days < 365:
                    return days
            except (ValueError, IndexError):
                pass

    for pat in TR_WEEK_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            try:
                weeks = int(m.group(1))
                if 0 < weeks < 52:
                    return weeks * 7
            except (ValueError, IndexError):
                pass

    for pat in TR_MONTH_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            try:
                months = int(m.group(1))
                if 0 < months <= 24:
                    return months * 30
            except (ValueError, IndexError):
                pass

    # Bare number as days (e.g. "5" for 5 days)
    m = re.search(r"^(\d{1,3})\s*$", t)
    if m:
        n = int(m.group(1))
        if 0 < n < 365:
            return n

    return None
