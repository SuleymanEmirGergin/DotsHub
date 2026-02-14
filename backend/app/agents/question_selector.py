"""Deterministic Question Selector.

Selects the most discriminative question from the question bank based on
disease candidate overlap. Falls back to None (triggering LLM fallback)
when no good question exists in the bank.

Algorithm:
    For each unasked symptom that appears in at least one candidate's symptom list:
        count = number of candidates that have this symptom
        disc(s) = 1.0 - abs(count / |C| - 0.5)
    Select symptom with highest disc score (most discriminative).
    Map to question bank for the Turkish question template.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)

# ─── Paths ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CACHE_DIR = _DATA_DIR / "kaggle_cache"


def _load_json(path: Path) -> Any:
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class QuestionSelector:
    """Deterministic discriminative question selection."""

    def __init__(self):
        self._question_bank: Dict[str, Dict] = {}  # canonical_symptom -> {question_tr, answer_type, priority_when_known?}
        self._kaggle_to_canonical: Dict[str, Optional[str]] = {}
        self._canonical_to_kaggle: Dict[str, List[str]] = {}
        self._skip_if_denied: Dict[str, List[str]] = {}  # canonical -> list of canonicals; if any denied, skip
        self._load()

    def _load(self):
        """Load question bank, mappings, and skip rules."""
        # Question bank (TR base)
        bank_data = _load_json(_DATA_DIR / "symptom_question_bank_tr.json")
        for q in bank_data.get("questions", []):
            self._question_bank[q["canonical_symptom"]] = {
                "question_tr": q["question_tr"],
                "answer_type": q.get("answer_type", "yes_no"),
                "choices_tr": q.get("choices_tr"),
                "priority_when_known": q.get("priority_when_known"),
            }
        # Merge EN translations when available
        en_data = _load_json(_DATA_DIR / "symptom_question_bank_en.json")
        for q in en_data.get("questions", []):
            canon = q.get("canonical_symptom")
            if canon and canon in self._question_bank:
                if q.get("question_en"):
                    self._question_bank[canon]["question_en"] = q["question_en"]
                if q.get("choices_en"):
                    self._question_bank[canon]["choices_en"] = q["choices_en"]

        # Skip rules: don't ask detail if parent symptom was denied
        skip_data = _load_json(_DATA_DIR / "question_skip_rules.json")
        for rule in skip_data.get("skip_rules", []):
            canon = rule.get("canonical_symptom")
            prereq = rule.get("skip_if_denied") or []
            if canon:
                self._skip_if_denied[canon] = prereq

        # Kaggle-to-canonical mapping
        self._kaggle_to_canonical = _load_json(_CACHE_DIR / "kaggle_to_canonical.json")
        for kaggle_sym, canonical in self._kaggle_to_canonical.items():
            if canonical is not None:
                if canonical not in self._canonical_to_kaggle:
                    self._canonical_to_kaggle[canonical] = []
                self._canonical_to_kaggle[canonical].append(kaggle_sym)

        logger.info(
            f"QuestionSelector loaded: {len(self._question_bank)} questions, "
            f"{len(self._canonical_to_kaggle)} canonical mappings"
        )

    def _kaggle_symptom_to_canonical(self, kaggle_sym: str) -> Optional[str]:
        """Convert a Kaggle symptom to its canonical Turkish form."""
        return self._kaggle_to_canonical.get(kaggle_sym)

    def select_question(
        self,
        disease_candidates: List[Dict[str, Any]],
        known_symptoms: Set[str],
        asked_symptoms: Set[str],
        denied_symptoms: Optional[Set[str]] = None,
        present_symptoms: Optional[Set[str]] = None,
        locale: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Select the most discriminative question.

        Args:
            disease_candidates: From candidate_generator.
            known_symptoms: Canonical symptoms already confirmed or denied (don't ask again).
            asked_symptoms: Canonical symptoms already asked about.
            denied_symptoms: Canonical symptoms user said no to; used for skip rules.
            present_symptoms: Canonical symptoms user said yes to; used for priority boost.
            locale: e.g. "tr-TR" or "en-US"; selects question_tr vs question_en (fallback: question_tr).

        Returns:
            Dict with "canonical_symptom", "question_tr", "answer_type"
            or None if no good question found (triggers LLM fallback).
        """
        C = len(disease_candidates)
        if C < 2:
            logger.info("QuestionSelector: fewer than 2 candidates, no discrimination needed")
            return None

        denied = denied_symptoms or set()
        present = present_symptoms or set()

        # Collect all symptoms across candidates (in Kaggle space)
        symptom_counts: Dict[str, int] = {}
        for candidate in disease_candidates:
            all_syms = set(candidate.get("matched_symptoms", []))
            all_syms.update(candidate.get("missing_symptoms", []))
            for sym in all_syms:
                if sym not in symptom_counts:
                    symptom_counts[sym] = 0
                symptom_counts[sym] += 1

        # Score each symptom for discriminative power
        candidates_scored = []
        for kaggle_sym, count in symptom_counts.items():
            canonical = self._kaggle_symptom_to_canonical(kaggle_sym)
            if canonical is None:
                continue
            if canonical in known_symptoms or canonical in asked_symptoms:
                continue
            if canonical not in self._question_bank:
                continue

            # Skip rule: if this question's prerequisite symptom was denied, skip
            skip_prereqs = self._skip_if_denied.get(canonical) or []
            if denied and skip_prereqs and any(p in denied for p in skip_prereqs):
                continue

            disc_score = 1.0 - abs(count / C - 0.5)

            # Priority boost: ask duration/related earlier when main symptom is present
            bank_entry = self._question_bank[canonical]
            priority_for = bank_entry.get("priority_when_known") or []
            if present and priority_for and any(p in present for p in priority_for):
                disc_score += 0.35

            candidates_scored.append({
                "canonical_symptom": canonical,
                "kaggle_symptom": kaggle_sym,
                "disc_score": disc_score,
                "count": count,
            })

        if not candidates_scored:
            logger.info("QuestionSelector: no suitable questions found in bank")
            return None

        # Deduplicate by canonical (keep highest disc_score per canonical)
        best_per_canonical: Dict[str, Dict] = {}
        for entry in candidates_scored:
            canonical = entry["canonical_symptom"]
            if canonical not in best_per_canonical or entry["disc_score"] > best_per_canonical[canonical]["disc_score"]:
                best_per_canonical[canonical] = entry

        # Sort: disc_score desc, then canonical alphabetical (deterministic)
        sorted_candidates = sorted(
            best_per_canonical.values(),
            key=lambda x: (-x["disc_score"], x["canonical_symptom"]),
        )

        best = sorted_candidates[0]
        bank_entry = self._question_bank[best["canonical_symptom"]]
        use_en = locale and str(locale).strip().lower().startswith("en")
        question_text = (bank_entry.get("question_en") if use_en else None) or bank_entry["question_tr"]
        choices = (bank_entry.get("choices_en") if use_en else None) or bank_entry.get("choices_tr")

        logger.info(
            f"QuestionSelector: selected '{best['canonical_symptom']}' "
            f"(disc={best['disc_score']:.2f}, count={best['count']}/{C})"
        )

        out = {
            "canonical_symptom": best["canonical_symptom"],
            "question_tr": question_text,
            "answer_type": bank_entry["answer_type"],
        }
        if choices:
            out["choices_tr"] = choices
        return out


# Singleton
question_selector = QuestionSelector()
