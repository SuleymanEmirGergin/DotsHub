"""Deterministic canonical extraction from Turkish free text.

Features:
  - Phrase-first matching (longer phrases have priority)
  - Word-boundary aware (regex)
  - Simple negation window (e.g. "ateş yok" → skip)
  - Works with the actual synonyms_tr.json array format

Adapted to the existing synonyms format:
  {
    "synonyms": [
      { "canonical": "baş ağrısı", "variants_tr": ["başım ağrıyor", ...] },
      ...
    ]
  }
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Set, Tuple

# Turkish-aware lowercase
TR_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})

# Default negation tokens
DEFAULT_NEGATIONS = ["yok", "değil", "hayır", "olmuyor", "olmadı", "değilim"]


def tr_lower(s: str) -> str:
    return s.translate(TR_LOWER_MAP).lower()


def normalize_text_tr(text: str) -> str:
    t = tr_lower(text)
    t = re.sub(r"[^\w\sçğıöşü]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_synonym_patterns(
    synonyms_json: Dict[str, Any],
) -> List[Tuple[str, re.Pattern]]:  # type: ignore[type-arg]
    """Build (canonical, compiled_pattern) list sorted by longest phrase first."""
    items: List[Tuple[str, str]] = []

    for entry in synonyms_json.get("synonyms", []):
        canonical = normalize_text_tr(entry.get("canonical", ""))
        if not canonical:
            continue
        for v in entry.get("variants_tr", []):
            vn = normalize_text_tr(v)
            if vn:
                items.append((canonical, vn))
        # Also match the canonical itself
        items.append((canonical, canonical))

    # Longer phrases first (more specific)
    items.sort(key=lambda x: len(x[1]), reverse=True)

    # De-duplicate
    seen: Set[str] = set()
    patterns: List[Tuple[str, re.Pattern]] = []  # type: ignore[type-arg]
    for canonical, phrase in items:
        key = f"{canonical}|{phrase}"
        if key in seen:
            continue
        seen.add(key)
        pat = re.compile(rf"\b{re.escape(phrase)}\b", flags=re.UNICODE)
        patterns.append((canonical, pat))

    return patterns


def is_negated(
    text_norm: str,
    start_idx: int,
    negations: List[str],
    window: int = 18,
) -> bool:
    """Check small window before match position for negation tokens."""
    left = text_norm[max(0, start_idx - window) : start_idx]
    for n in negations:
        nn = normalize_text_tr(n)
        if nn and re.search(rf"\b{re.escape(nn)}\b", left):
            return True
    return False


def extract_canonicals_tr(
    text_tr: str,
    answers: Dict[str, str],
    synonyms_json: Dict[str, Any],
) -> List[str]:
    """
    Deterministic canonical extraction from:
      - free text (text_tr)
      - structured answers (answer keys as canonicals)

    Returns unique canonicals, sorted for stability.
    """
    text_norm = normalize_text_tr(text_tr)
    negations = DEFAULT_NEGATIONS

    patterns = build_synonym_patterns(synonyms_json)

    found: Set[str] = set()

    # 1) Extract from free text
    for canonical, pat in patterns:
        for m in pat.finditer(text_norm):
            if is_negated(text_norm, m.start(), negations):
                continue
            found.add(canonical)
            break  # one match per canonical is enough

    # 2) Add answer keys as canonicals
    for k in (answers or {}):
        kn = normalize_text_tr(k)
        if kn:
            found.add(kn)

    return sorted(found)
