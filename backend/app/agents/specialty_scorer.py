"""Specialty Scoring Engine V2 — Deterministic with synonym support.

Uses synonyms_tr.json for canonical mapping + NO_DOUBLE_COUNT_SAME_CANONICAL policy.
Phrase match > keyword match priority. Tie-break: keyword_score then alphabetical.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

logger = logging.getLogger(__name__)

# ─── Load data files ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(name: str) -> dict:
    with open(_DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


_keywords_data = _load_json("specialty_keywords_tr.json")
_synonyms_data = _load_json("synonyms_tr.json")
_specialties = _keywords_data["specialties"]
_scoring = _keywords_data["scoring"]

KEYWORD_POINTS = int(_scoring["keyword_match_points"])      # 3
PHRASE_POINTS = int(_scoring["phrase_match_points"])          # 5
NEGATIVE_PENALTY = int(_scoring["negative_keyword_penalty"])  # -4


# ─── Normalization ───

def normalize_tr(text: str) -> str:
    """Deterministic Turkish text normalization.

    Handles Turkish-specific case folding:
    - İ → i (Turkish capital I with dot)
    - I → ı (Turkish capital I without dot)
    """
    # Turkish-specific case folding before generic lowercase
    text = text.replace("İ", "i").replace("I", "ı")
    text = text.lower().strip()
    text = re.sub(r"""[.,;:!?(){}\[\]"'`~]""", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _unique(seq: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


# ─── Synonym Index ───

def _build_synonym_index() -> Tuple[List[Tuple[str, str]], Set[str]]:
    """Build sorted variant -> canonical index from synonyms_tr.json.

    Variants are sorted longest-first for deterministic longest-match.
    """
    variants: List[Tuple[str, str]] = []
    for s in _synonyms_data["synonyms"]:
        canonical = s["canonical"].lower()
        for v in s["variants_tr"]:
            variants.append((v.lower(), canonical))
    # longest first, then lexicographic for determinism
    variants.sort(key=lambda x: (-len(x[0]), x[0]))
    canonical_set = {s["canonical"].lower() for s in _synonyms_data["synonyms"]}
    return variants, canonical_set


_variant_index, _canonical_set = _build_synonym_index()


# ─── Score Data Classes ───

class SpecialtyScore:
    """Score for a single specialty with debug info."""

    def __init__(self, specialty_id: str, specialty_tr: str):
        self.id = specialty_id
        self.specialty_tr = specialty_tr
        self.score: int = 0
        self.phrase_score: int = 0
        self.keyword_score: int = 0
        self.negative_penalties: int = 0
        self.matched_phrases_tr: List[str] = []
        self.matched_keywords_tr: List[str] = []
        self.matched_canonicals: List[str] = []
        self.hits: List[Dict[str, Any]] = []

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "phrase_score": self.phrase_score,
            "keyword_score": self.keyword_score,
            "negative_penalties": self.negative_penalties,
            "matched_phrases_tr": self.matched_phrases_tr,
            "matched_keywords_tr": self.matched_keywords_tr,
            "matched_canonicals": sorted(self.matched_canonicals),
        }


class SpecialtyScorer:
    """Deterministic specialty scorer with synonym support.

    Scoring pipeline:
    1. Normalize text (lowercase, punctuation→space, whitespace collapse)
    2. Detect phrases via synonym variants (longest-first)
    3. Map to canonical forms (NO_DOUBLE_COUNT_SAME_CANONICAL)
    4. For each specialty:
       a. Phrase scoring: if canonical (or phrase literal) is in specialty keywords → +5 per canonical
       b. Keyword scoring: remaining canonicals in specialty keywords → +3 per canonical
       c. Negative penalties: negative keywords in text → -4 each
    5. Deterministic sorting: score desc → keyword_score desc → alphabetical id
    """

    def __init__(self):
        self._specialties = _specialties

    def score_text(
        self,
        text: str,
        existing_scores: Optional[Dict[str, dict]] = None,
    ) -> Dict[str, SpecialtyScore]:
        """Score text deterministically against all specialties.

        Args:
            text: User message (Turkish free-text)
            existing_scores: Previous scores to accumulate on (from prior messages)

        Returns:
            Dict mapping specialty_id -> SpecialtyScore
        """
        normalized = normalize_tr(text)

        # ── Step 1: Phrase detection via synonym variants ──
        matched_phrases: List[Tuple[str, str]] = []   # (phrase_text, canonical)
        canonical_locked: Set[str] = set()

        for variant, canonical in _variant_index:
            if variant in normalized:
                matched_phrases.append((variant, canonical))
                canonical_locked.add(canonical)

        # ── Step 2: Direct canonical keywords in text (not locked by phrase) ──
        matched_keywords: List[str] = []
        for canonical in sorted(_canonical_set):  # sorted for determinism
            if canonical in normalized and canonical not in canonical_locked:
                matched_keywords.append(canonical)
                canonical_locked.add(canonical)

        phrase_canonicals = _unique([c for _, c in matched_phrases])
        keyword_canonicals = _unique(matched_keywords)

        # ── Step 3: Score each specialty ──
        scores: Dict[str, SpecialtyScore] = {}

        for spec in self._specialties:
            sid = spec["id"]
            sname = spec["specialty_tr"]
            keywords_set = {k.lower() for k in spec["keywords_tr"]}
            negatives = [n.lower() for n in spec.get("negative_keywords_tr", [])]

            score_obj = SpecialtyScore(sid, sname)

            # Restore previous scores if accumulating
            if existing_scores and sid in existing_scores:
                prev = existing_scores[sid]
                score_obj.score = prev.get("score", 0)
                score_obj.phrase_score = prev.get("phrase_score", 0)
                score_obj.keyword_score = prev.get("keyword_score", 0)
                score_obj.negative_penalties = prev.get("negative_penalties", 0)
                score_obj.matched_phrases_tr = list(prev.get("matched_phrases_tr", []))
                score_obj.matched_keywords_tr = list(prev.get("matched_keywords_tr", []))
                score_obj.matched_canonicals = list(prev.get("matched_canonicals", []))

            scored_canonicals: Set[str] = set(score_obj.matched_canonicals)

            # Phrase scoring (once per canonical, phrase > keyword)
            for canonical in phrase_canonicals:
                rep_phrase = next((p for p, c in matched_phrases if c == canonical), None)
                phrase_matches_specialty = (
                    canonical in keywords_set
                    or (rep_phrase in keywords_set if rep_phrase else False)
                )

                if phrase_matches_specialty and canonical not in scored_canonicals:
                    score_obj.score += PHRASE_POINTS
                    score_obj.phrase_score += PHRASE_POINTS
                    scored_canonicals.add(canonical)
                    if rep_phrase and rep_phrase not in score_obj.matched_phrases_tr:
                        score_obj.matched_phrases_tr.append(rep_phrase)
                    score_obj.hits.append({
                        "kind": "phrase", "value": rep_phrase or canonical, "points": PHRASE_POINTS
                    })

            # Keyword scoring (canonicals not already scored by phrase)
            for canonical in keyword_canonicals:
                if canonical in keywords_set and canonical not in scored_canonicals:
                    score_obj.score += KEYWORD_POINTS
                    score_obj.keyword_score += KEYWORD_POINTS
                    scored_canonicals.add(canonical)
                    if canonical not in score_obj.matched_keywords_tr:
                        score_obj.matched_keywords_tr.append(canonical)
                    score_obj.hits.append({
                        "kind": "keyword", "value": canonical, "points": KEYWORD_POINTS
                    })

            # Also check raw text against specialty keywords for non-synonym matches
            for kw in spec["keywords_tr"]:
                kw_lower = kw.lower()
                if kw_lower in normalized and kw_lower not in scored_canonicals:
                    # Check if this is a phrase (multi-word) or keyword
                    if " " in kw_lower:
                        score_obj.score += PHRASE_POINTS
                        score_obj.phrase_score += PHRASE_POINTS
                        scored_canonicals.add(kw_lower)
                        if kw_lower not in score_obj.matched_phrases_tr:
                            score_obj.matched_phrases_tr.append(kw_lower)
                        score_obj.hits.append({
                            "kind": "phrase", "value": kw_lower, "points": PHRASE_POINTS
                        })
                    else:
                        score_obj.score += KEYWORD_POINTS
                        score_obj.keyword_score += KEYWORD_POINTS
                        scored_canonicals.add(kw_lower)
                        if kw_lower not in score_obj.matched_keywords_tr:
                            score_obj.matched_keywords_tr.append(kw_lower)
                        score_obj.hits.append({
                            "kind": "keyword", "value": kw_lower, "points": KEYWORD_POINTS
                        })

            # Negative penalties
            for neg in negatives:
                if neg and neg in normalized:
                    score_obj.score += NEGATIVE_PENALTY
                    score_obj.negative_penalties += NEGATIVE_PENALTY
                    score_obj.hits.append({
                        "kind": "negative", "value": neg, "points": NEGATIVE_PENALTY
                    })

            score_obj.matched_canonicals = sorted(scored_canonicals)
            scores[sid] = score_obj

        return scores

    def get_top_specialty(self, scores: Dict[str, SpecialtyScore]) -> Optional[Dict[str, Any]]:
        """Get the highest-scoring specialty with deterministic tie-breaking.

        Tie-break order:
        1. Higher score
        2. Higher keyword_score
        3. Alphabetical id (deterministic final)
        4. Fallback to Dahiliye if all zero
        """
        if not scores:
            return None

        sorted_scores = sorted(
            scores.values(),
            key=lambda s: (-s.score, -s.keyword_score, s.id),
        )

        top = sorted_scores[0]
        if top.score <= 0:
            return {"id": "internal_gi", "specialty_tr": "Dahiliye", "score": 0}

        # Detect tie
        tie = (
            len(sorted_scores) > 1
            and sorted_scores[0].score == sorted_scores[1].score
            and sorted_scores[0].keyword_score == sorted_scores[1].keyword_score
        )

        return {
            "id": top.id,
            "specialty_tr": top.specialty_tr,
            "score": top.score,
            "tie": tie,
        }

    def scores_to_dict(self, scores: Dict[str, SpecialtyScore]) -> Dict[str, dict]:
        """Convert SpecialtyScore objects to serializable dicts."""
        return {sid: s.to_dict() for sid, s in scores.items()}


# Singleton
specialty_scorer = SpecialtyScorer()
