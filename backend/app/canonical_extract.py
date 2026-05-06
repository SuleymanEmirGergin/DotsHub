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
from typing import Any, Dict, List, Optional, Set, Tuple

# Turkish-aware lowercase
TR_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})

# Default negation tokens
DEFAULT_NEGATIONS = ["yok", "değil", "hayır", "olmuyor", "olmadı", "değilim"]

# Adversative conjunctions that flip polarity in Turkish. Used by
# is_negated() as clause boundaries when scanning around a match —
# negation in the next/previous clause must NOT bleed across.
_NEGATION_BOUNDARY_RE = re.compile(r"\b(?:ama|fakat|ancak)\b")


def tr_lower(s: str) -> str:
    return s.translate(TR_LOWER_MAP).lower()


def normalize_text_tr(text: str) -> str:
    t = tr_lower(text)
    t = re.sub(r"[^\w\sçğıöşü]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_synonym_patterns(
    synonyms_json: Dict[str, Any],
) -> List[Tuple[str, "re.Pattern[str]"]]:
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
    patterns: List[Tuple[str, "re.Pattern[str]"]] = []
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
    end_idx: Optional[int] = None,
) -> bool:
    """Check window around a match position for negation tokens.

    Scans both LEFT (before start_idx) and RIGHT (after end_idx). Each
    side is capped at `window` characters and additionally truncated at
    the nearest adversative conjunction (ama/fakat/ancak), so negation
    in an adjacent clause doesn't bleed in — e.g. "ateş var ama soğuk
    algınlığı yok" leaves "ateş" positive.

    Right-side scan matters because Turkish is predicate-final: the
    natural negation form is postfix ("ateş yok"), not prefix.

    `end_idx` defaults to `start_idx` (right-side window collapses to
    zero) to preserve the historical left-only signature for callers
    that don't supply a match end. Production callers pass `m.end()`.
    """
    # LEFT window: text immediately before the match, optionally
    # truncated AFTER the latest adversative conjunction.
    left = text_norm[max(0, start_idx - window) : start_idx]
    boundary_left = list(_NEGATION_BOUNDARY_RE.finditer(left))
    if boundary_left:
        left = left[boundary_left[-1].end() :]

    # RIGHT window: text immediately after the match, optionally
    # truncated BEFORE the earliest adversative conjunction. Skipped
    # entirely when end_idx is None — preserves the historical left-
    # only contract for callers that only have a start position.
    if end_idx is None:
        right = ""
    else:
        right = text_norm[end_idx : end_idx + window]
        boundary_right = _NEGATION_BOUNDARY_RE.search(right)
        if boundary_right:
            right = right[: boundary_right.start()]

    for n in negations:
        nn = normalize_text_tr(n)
        if not nn:
            continue
        nn_pat = rf"\b{re.escape(nn)}\b"
        if re.search(nn_pat, left) or re.search(nn_pat, right):
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
            if is_negated(text_norm, m.start(), negations, end_idx=m.end()):
                continue
            found.add(canonical)
            break  # one match per canonical is enough

    # 2) Add answer keys as canonicals
    for k in (answers or {}):
        kn = normalize_text_tr(k)
        if kn:
            found.add(kn)

    return sorted(found)
