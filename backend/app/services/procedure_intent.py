"""Procedure-intent extraction from free-text user input.

What this is
    First-line resolver for the health-tourism quote flow. The user
    types something like *"saçım dökülüyor"* or *"burnumdan memnun
    değilim"*; this module returns the matching procedure id
    (``fue_hair_transplant``, ``rhinoplasty``) along with a confidence
    score and the synonym(s) that triggered the match.

Why deterministic-first
    Same reason the existing triage layer is rule-driven: predictable,
    explainable, audit-able. The synonym registry lives in
    ``procedures.json`` next to the procedure definition — adding a
    new way users describe a procedure means editing one file.

What this is NOT
    An LLM call. The downstream module (``llm_nlu``) can be invoked
    when this resolver returns None or low confidence; that wiring is
    deliberately separate so the cheap path runs first.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import NamedTuple, Optional

from app.services import procedure_catalog

logger = logging.getLogger(__name__)

# Tokens shorter than this don't count toward a synonym hit. Stops
# common words like "iyi", "yok", "of" from matching anything.
_MIN_TOKEN_LEN = 3


class ProcedureMatch(NamedTuple):
    procedure_id: str
    confidence_0_1: float
    matched_synonyms: list[str]


def _normalise(text: str) -> str:
    """Lowercase + strip punctuation but keep Turkish characters and
    inner whitespace. Synonym index is also lowercased so this is
    fold-symmetric."""
    text = text.lower()
    # Replace punctuation with spaces so "saçım, dökülüyor!" tokenises
    # cleanly. Keep letters (incl. Turkish ÇĞİÖŞÜ), digits, whitespace.
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def extract(
    user_message: Optional[str], locale: Optional[str] = None
) -> Optional[ProcedureMatch]:
    """Return the best procedure match, or None if no synonyms hit.

    Confidence is a simple ratio: how many of the input's tokens
    matched a synonym for the winning procedure, normalised by the
    total token count. It's a coarse signal — good enough to decide
    "send straight to quote" vs "ask a clarifying question".
    """
    if not user_message or not user_message.strip():
        return None
    text = _normalise(user_message)
    if len(text) < _MIN_TOKEN_LEN:
        return None

    # Count multi-word synonym hits per procedure. Substring match is
    # intentional — "saç ekimi" should hit even when surrounded by
    # other words ("saç ekimi olmak istiyorum"). Single-word synonyms
    # are bounded by token edges to avoid false matches inside longer
    # words ("ivf" vs "ivfyou").
    hits: Counter[str] = Counter()
    matched: dict[str, list[str]] = {}

    for syn, proc_id in procedure_catalog.synonyms(locale):
        syn_norm = _normalise(syn)
        if not syn_norm or len(syn_norm) < _MIN_TOKEN_LEN:
            continue
        if " " in syn_norm:
            # Multi-word phrase — substring match.
            if syn_norm in text:
                hits[proc_id] += 2  # phrase matches weigh more
                matched.setdefault(proc_id, []).append(syn)
        else:
            # Single token — require word boundary.
            if re.search(rf"\b{re.escape(syn_norm)}\b", text):
                hits[proc_id] += 1
                matched.setdefault(proc_id, []).append(syn)

    if not hits:
        return None

    # Winner is the procedure with the most hits; ties broken by
    # alphabetical id so the resolver is deterministic across runs.
    best_id, best_score = max(
        hits.items(), key=lambda kv: (kv[1], -ord(kv[0][0]))
    )
    total_tokens = max(len(text.split()), 1)
    # Cap confidence at 0.95 — leaves headroom for a future LLM
    # enhancement that returns 1.0 only with full semantic match.
    confidence = min(0.95, best_score / total_tokens)

    return ProcedureMatch(
        procedure_id=best_id,
        confidence_0_1=round(confidence, 3),
        matched_synonyms=matched.get(best_id, []),
    )
