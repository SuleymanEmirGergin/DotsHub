"""Deterministic synonym suggestion engine.

Analyzes down-feedback sessions to find tokens that appear in user text
but weren't captured by any canonical. These are synonym candidates.

Used by tuning_report to produce actionable suggestions for expanding
config/synonyms_tr.json.
"""

from __future__ import annotations
import re
from collections import Counter
from typing import Any, Dict, List, Optional

STOPWORDS = {
    "ve", "ama", "çok", "bir", "bu", "şu", "var", "yok", "için", "gibi",
    "daha", "olan", "oldu", "oluyor", "olmuyor", "benim", "bende", "bana",
    "beni", "başka", "kadar", "sonra", "önce", "şimdi", "hala", "bile",
}


def tokenize_tr(text: str) -> List[str]:
    """Tokenize Turkish text into lowercased words (4+ chars, no stopwords)."""
    t = text.lower()
    t = re.sub(r"[^\w\sçğıöşü]", " ", t)
    return [w for w in t.split() if len(w) >= 4 and w not in STOPWORDS]


def suggest_synonyms_from_down_sessions(
    sessions: List[Dict[str, Any]],
    min_count: int = 3,
) -> List[Dict[str, Any]]:
    """
    Find tokens that appear frequently in down-feedback sessions
    but weren't captured as canonicals.

    Returns sorted list of { token, support_count }.
    """
    counter: Counter = Counter()

    for s in sessions:
        text = s.get("input_text") or ""
        canonicals = set(c.lower() for c in (s.get("user_canonicals_tr") or []))
        tokens = tokenize_tr(text)

        for tok in tokens:
            if tok not in canonicals:
                counter[tok] += 1

    suggestions = []
    for tok, cnt in counter.items():
        if cnt >= min_count:
            suggestions.append({"token": tok, "support_count": cnt})

    return sorted(suggestions, key=lambda x: x["support_count"], reverse=True)


def map_token_to_canonical(
    token: str,
    sessions: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Heuristic: if token co-occurs with a canonical across sessions,
    the most frequent co-occurring canonical is the likely mapping.
    """
    freq: Counter = Counter()
    for s in sessions:
        if token in (s.get("input_text") or "").lower():
            for c in s.get("user_canonicals_tr") or []:
                freq[c.lower()] += 1
    if not freq:
        return None
    return freq.most_common(1)[0][0]
