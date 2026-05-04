"""Phase-3 Information-gain question selector.

Given the current candidate distribution and per-disease symptom sets,
pick the symptom whose Y/N answer maximally splits the candidate
distribution — i.e. minimizes the expected entropy of the posterior.

Falls back to None if no useful split exists; caller then defers to the
existing deterministic question_selector.

Activated by env flag INFO_GAIN_SELECTOR_ENABLED=1 — default OFF.
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CACHE_DIR = _DATA_DIR / "kaggle_cache"


def is_enabled() -> bool:
    return os.getenv("INFO_GAIN_SELECTOR_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class InfoGainSelector:
    """Selects the next yes/no symptom question by maximum information gain.

    Symptom space here is the **Kaggle EN symptom space** (as used by the
    candidate matrix). The mapping from these to TR canonical labels lives
    in kaggle_to_canonical.json — we use it to surface a TR question.
    """

    def __init__(self) -> None:
        self._loaded = False
        self._disease_symptoms: Dict[str, List[str]] = {}
        self._kaggle_to_canonical: Dict[str, Optional[str]] = {}
        self._question_bank_tr: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        ds = _load_json(_CACHE_DIR / "disease_symptoms.json") or {}
        self._disease_symptoms = {k: list(v) for k, v in ds.items()}
        self._kaggle_to_canonical = _load_json(_CACHE_DIR / "kaggle_to_canonical.json") or {}
        bank = _load_json(_DATA_DIR / "symptom_question_bank_tr.json") or {}
        for entry in bank.get("questions", []):
            cs = entry.get("canonical_symptom")
            if cs:
                self._question_bank_tr[cs] = entry
        self._loaded = bool(self._disease_symptoms)
        if self._loaded:
            logger.info(
                f"[InfoGainSelector] loaded: {len(self._disease_symptoms)} diseases, "
                f"{len(self._question_bank_tr)} TR question templates"
            )
        else:
            logger.warning("[InfoGainSelector] disease_symptoms.json missing — disabled")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def select(
        self,
        candidate_weights: List[Tuple[str, float]],
        already_asked_canonical: Set[str],
        confirmed_present: Set[str],
        confirmed_absent: Set[str],
    ) -> Optional[Dict[str, Any]]:
        """Pick the next yes/no symptom question.

        Args:
          candidate_weights: [(disease_label, weight)] — weight is e.g.
            confidence_0_1 from clinician or score_0_1 from Jaccard. Need
            not sum to 1; we normalize.
          already_asked_canonical: TR canonical labels already asked.
          confirmed_present / confirmed_absent: TR canonical labels with
            known answer (used to skip).

        Returns:
          {"canonical_symptom": str, "question_tr": str, "info_gain": float,
           "split": {"yes_mass": float, "no_mass": float}}
          or None if no useful question exists.
        """
        if not self._loaded or not candidate_weights:
            return None

        total_w = sum(max(0.0, w) for _, w in candidate_weights)
        if total_w <= 0:
            return None

        weighted = [(d, max(0.0, w) / total_w) for d, w in candidate_weights]
        prior_h = self._entropy([w for _, w in weighted])

        skip = set(already_asked_canonical) | set(confirmed_present) | set(confirmed_absent)

        # Build candidate symptom space as union of candidate diseases' symptoms,
        # mapped to TR canonical labels (skip ones without a TR mapping or template).
        symptom_to_disease_mass: Dict[str, float] = {}  # canonical_tr -> total weight of diseases that have it
        symptom_to_kaggle: Dict[str, str] = {}  # for logging
        for disease, weight in weighted:
            symptoms = self._disease_symptoms.get(disease, [])
            for s in symptoms:
                tr = self._kaggle_to_canonical.get(s)
                if not tr or tr in skip:
                    continue
                if tr not in self._question_bank_tr:
                    continue  # no TR question template available
                symptom_to_disease_mass[tr] = symptom_to_disease_mass.get(tr, 0.0) + weight
                symptom_to_kaggle[tr] = s

        if not symptom_to_disease_mass:
            return None

        best: Optional[Tuple[float, str, float, float]] = None  # (gain, canonical, yes_mass, no_mass)

        for canonical, yes_mass in symptom_to_disease_mass.items():
            no_mass = 1.0 - yes_mass
            if yes_mass <= 1e-9 or no_mass <= 1e-9:
                continue  # uninformative — every / no candidate has it

            # Expected entropy after answer
            h_yes = self._cond_entropy(weighted, canonical, answer_yes=True)
            h_no = self._cond_entropy(weighted, canonical, answer_yes=False)
            expected_h = yes_mass * h_yes + no_mass * h_no
            gain = prior_h - expected_h
            if gain <= 0:
                continue

            if best is None or gain > best[0]:
                best = (gain, canonical, yes_mass, no_mass)

        if best is None:
            return None

        gain, canonical, yes_mass, no_mass = best
        template = self._question_bank_tr.get(canonical, {})
        return {
            "canonical_symptom": canonical,
            "question_tr": template.get("question_tr", f"{canonical} var mı?"),
            "answer_type": template.get("answer_type", "yes_no"),
            "choices_tr": template.get("choices_tr"),
            "info_gain": round(gain, 4),
            "split": {"yes_mass": round(yes_mass, 3), "no_mass": round(no_mass, 3)},
        }

    @staticmethod
    def _entropy(probs: List[float]) -> float:
        return -sum(p * math.log2(p) for p in probs if p > 0)

    def _cond_entropy(
        self,
        weighted: List[Tuple[str, float]],
        canonical_symptom: str,
        answer_yes: bool,
    ) -> float:
        """Posterior entropy assuming the user answers yes/no to `canonical_symptom`.

        We use a hard split: a candidate disease is consistent with the
        answer iff (canonical in disease's mapped TR symptom set) == answer_yes.
        """
        masses: List[float] = []
        for disease, w in weighted:
            symptoms = self._disease_symptoms.get(disease, [])
            disease_canonicals = {self._kaggle_to_canonical.get(s) for s in symptoms}
            disease_canonicals.discard(None)
            has_it = canonical_symptom in disease_canonicals
            if has_it == answer_yes:
                masses.append(w)

        total = sum(masses)
        if total <= 0:
            return 0.0
        norm = [m / total for m in masses]
        return self._entropy(norm)


info_gain_selector = InfoGainSelector()
