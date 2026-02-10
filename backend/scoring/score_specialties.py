"""Python reference implementation — Deterministic specialty scoring.

Usage:
    python score_specialties.py

Reads from ../app/data/synonyms_tr.json and ../app/data/specialty_keywords_tr.json
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Default paths (relative to this file)
_HERE = Path(__file__).resolve().parent
_DEFAULT_SYNONYMS = _HERE.parent / "app" / "data" / "synonyms_tr.json"
_DEFAULT_KEYWORDS = _HERE.parent / "app" / "data" / "specialty_keywords_tr.json"


def normalize_tr(text: str) -> str:
    """Turkish-aware normalization with proper İ/I case folding."""
    text = text.replace("\u0130", "i").replace("I", "\u0131")  # İ→i, I→ı
    text = text.lower().strip()
    text = re.sub(r"""[.,;:!?(){}\[\]"'`~]""", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def unique(seq: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


@dataclass
class SpecialtyScore:
    id: str
    specialty_tr: str
    score: int
    phrase_score: int
    keyword_score: int
    negative_penalties: int
    matched_phrases_tr: List[str]
    matched_keywords_tr: List[str]
    matched_canonicals: List[str]
    debug: Dict[str, Any]


def build_synonym_index(syn: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], Set[str]]:
    variants: List[Tuple[str, str]] = []
    for s in syn["synonyms"]:
        canonical = s["canonical"].lower()
        for v in s["variants_tr"]:
            variants.append((v.lower(), canonical))
    # longest first, then lexicographic for determinism
    variants.sort(key=lambda x: (-len(x[0]), x[0]))
    canonical_set = {s["canonical"].lower() for s in syn["synonyms"]}
    return variants, canonical_set


def score_specialties_deterministic(
    text_tr: str,
    synonyms_path: str = str(_DEFAULT_SYNONYMS),
    specialty_keywords_path: str = str(_DEFAULT_KEYWORDS),
) -> Dict[str, Any]:
    syn = load_json(synonyms_path)
    spec = load_json(specialty_keywords_path)

    variants, canonical_set = build_synonym_index(syn)
    normalized = normalize_tr(text_tr)

    matched_phrases: List[Tuple[str, str]] = []  # (phrase, canonical)
    canonical_locked: Set[str] = set()

    # 1) phrase detection
    for variant, canonical in variants:
        if variant in normalized:
            matched_phrases.append((variant, canonical))
            canonical_locked.add(canonical)

    # 2) canonical keywords from raw text (not locked already)
    matched_keywords: List[str] = []
    for canonical in sorted(canonical_set):  # sorted for determinism
        if canonical in normalized and canonical not in canonical_locked:
            matched_keywords.append(canonical)
            canonical_locked.add(canonical)

    phrase_canonicals = unique([c for _, c in matched_phrases])
    keyword_canonicals = unique(matched_keywords)

    keyword_points = int(spec["scoring"]["keyword_match_points"])
    phrase_points = int(spec["scoring"]["phrase_match_points"])
    neg_penalty = int(spec["scoring"]["negative_keyword_penalty"])

    scores: List[SpecialtyScore] = []

    for s in spec["specialties"]:
        sid = s["id"]
        sname = s["specialty_tr"]
        keywords = {k.lower() for k in s["keywords_tr"]}
        negatives = [n.lower() for n in s.get("negative_keywords_tr", [])]

        score = 0
        phrase_score = 0
        keyword_score = 0
        negative_penalties = 0
        scored_canonicals: Set[str] = set()
        matched_phr_out: List[str] = []
        matched_kw_out: List[str] = []
        hits: List[Dict[str, Any]] = []

        # phrase scoring (once per canonical)
        for canonical in phrase_canonicals:
            rep_phrase = next((p for p, c in matched_phrases if c == canonical), None)
            phrase_matches = (canonical in keywords) or (rep_phrase in keywords if rep_phrase else False)

            if phrase_matches and canonical not in scored_canonicals:
                score += phrase_points
                phrase_score += phrase_points
                scored_canonicals.add(canonical)
                if rep_phrase:
                    matched_phr_out.append(rep_phrase)
                hits.append({"kind": "phrase", "value": rep_phrase or canonical, "points": phrase_points})

        # keyword scoring (canonicals not already scored)
        for canonical in keyword_canonicals:
            if canonical in keywords and canonical not in scored_canonicals:
                score += keyword_points
                keyword_score += keyword_points
                scored_canonicals.add(canonical)
                matched_kw_out.append(canonical)
                hits.append({"kind": "keyword", "value": canonical, "points": keyword_points})

        # negative penalties
        for neg in negatives:
            if neg and neg in normalized:
                score += neg_penalty
                negative_penalties += neg_penalty
                hits.append({"kind": "negative", "value": neg, "points": neg_penalty})

        scores.append(SpecialtyScore(
            id=sid,
            specialty_tr=sname,
            score=score,
            phrase_score=phrase_score,
            keyword_score=keyword_score,
            negative_penalties=negative_penalties,
            matched_phrases_tr=unique(matched_phr_out),
            matched_keywords_tr=unique(matched_kw_out),
            matched_canonicals=sorted(scored_canonicals),
            debug={"normalized_text": normalized, "hits": hits},
        ))

    # deterministic ordering
    scores.sort(key=lambda x: (-x.score, -x.keyword_score, x.id))

    tie = False
    if len(scores) > 1 and scores[0].score == scores[1].score and scores[0].keyword_score == scores[1].keyword_score:
        tie = True

    return {
        "normalized_text": normalized,
        "top": asdict(scores[0]) if scores else None,
        "scores": [asdict(s) for s in scores],
        "tie": tie,
    }


if __name__ == "__main__":
    test_cases = [
        "Sabah kalktığımdan beri başım dönüyor, midem bulanıyor.",
        "3 gündür boğazım ağrıyor, ateşim var, yutkunurken yanıyor.",
        "Göğsümde baskı var, nefesim daralıyor ve terliyorum.",
        "İdrar yaparken yanıyor, çok sık tuvalete çıkıyorum.",
        "Vücudumda kaşıntılı döküntü çıktı.",
    ]

    for text in test_cases:
        res = score_specialties_deterministic(text)
        top = res["top"]
        print(f"\nInput: {text}")
        print(f"  Top: {top['specialty_tr']} (score={top['score']}, tie={res['tie']})")
        for s in res["scores"][:3]:
            if s["score"] > 0:
                print(f"    {s['specialty_tr']}: {s['score']}")
