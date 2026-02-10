"""Simple deterministic duration parser for Turkish symptom text."""

from __future__ import annotations

import re
from typing import Optional

TR_DAY_PATTERNS = [
    r"(\d+)\s*g[uÃƒÂ¼]nd[ÃƒÂ¼u]r",  # 2 gÃƒÂ¼ndÃƒÂ¼r
    r"(\d+)\s*g[uÃƒÂ¼]n",  # 2 gÃƒÂ¼n
    r"(\d+)\s*g[uÃƒÂ¼]n\s*oldu",
    r"(\d+)\s*g[uÃƒÂ¼]nl[ÃƒÂ¼u]k",  # 2 gÃƒÂ¼nlÃƒÂ¼k
]


def extract_duration_days(text: str) -> Optional[int]:
    t = (text or "").lower()
    for pat in TR_DAY_PATTERNS:
        m = re.search(pat, t)
        if not m:
            continue
        try:
            days = int(m.group(1))
        except Exception:
            continue
        if 0 < days < 365:
            return days

    m2 = re.search(r"(\d+)\s*hafta", t)
    if m2:
        try:
            weeks = int(m2.group(1))
        except Exception:
            return None
        if 0 < weeks < 52:
            return weeks * 7

    return None
