"""Layer A: Deterministic Disease Candidate Generator.

Uses weighted Jaccard similarity to score user symptoms against the
disease-symptom matrix (from preprocessed Kaggle data).

Operates entirely on canonical symptom names (Turkish).
Maps user canonicals -> Kaggle symptom space via kaggle_to_canonical.json (reverse).
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)

# ─── Paths ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CACHE_DIR = _DATA_DIR / "kaggle_cache"


def _load_json(path: Path) -> dict:
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class CandidateGenerator:
    """Weighted Jaccard similarity engine for disease candidate generation."""

    def __init__(self):
        self._loaded = False
        self._disease_symptoms: Dict[str, List[str]] = {}
        self._symptom_severity: Dict[str, int] = {}
        self._config: Dict[str, Any] = {}
        self._canonical_to_kaggle: Dict[str, List[str]] = {}  # canonical_tr -> [kaggle_symptom, ...]
        self._load()

    def _load(self):
        """Load all data files."""
        # Config
        config_path = _DATA_DIR / "candidate_generator.json"
        self._config = _load_json(config_path)

        # Disease-symptom matrix
        self._disease_symptoms = _load_json(_CACHE_DIR / "disease_symptoms.json")

        # Severity weights
        self._symptom_severity = _load_json(_CACHE_DIR / "symptom_severity.json")

        # Build reverse mapping: canonical_tr -> [kaggle_symptom, ...]
        kaggle_to_canonical = _load_json(_CACHE_DIR / "kaggle_to_canonical.json")
        self._canonical_to_kaggle = {}
        for kaggle_sym, canonical in kaggle_to_canonical.items():
            if canonical is not None:
                if canonical not in self._canonical_to_kaggle:
                    self._canonical_to_kaggle[canonical] = []
                self._canonical_to_kaggle[canonical].append(kaggle_sym)

        if self._disease_symptoms:
            self._loaded = True
            logger.info(
                f"CandidateGenerator loaded: {len(self._disease_symptoms)} diseases, "
                f"{len(self._symptom_severity)} severity entries, "
                f"{len(self._canonical_to_kaggle)} canonical mappings"
            )
        else:
            logger.warning("CandidateGenerator: no disease data loaded (run preprocess_kaggle.py first)")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _get_weight(self, symptom: str) -> float:
        """Get weight for a symptom: default + severity * multiplier."""
        default_w = self._config.get("weights", {}).get("default_symptom_weight", 1.0)
        use_severity = self._config.get("weights", {}).get("use_severity_if_available", True)
        severity_mult = self._config.get("weights", {}).get("severity_weight_multiplier", 0.25)

        if use_severity and symptom in self._symptom_severity:
            return default_w + self._symptom_severity[symptom] * severity_mult
        return default_w

    def _canonical_to_kaggle_set(self, canonical_symptoms: Set[str]) -> Set[str]:
        """Convert user's canonical Turkish symptoms to Kaggle symptom space."""
        kaggle_set = set()
        for canonical in canonical_symptoms:
            if canonical in self._canonical_to_kaggle:
                kaggle_set.update(self._canonical_to_kaggle[canonical])
            else:
                # Try direct match (some canonicals might be Kaggle names already)
                norm = canonical.lower().replace(" ", "_")
                if norm in self._symptom_severity or any(
                    norm in syms for syms in self._disease_symptoms.values()
                ):
                    kaggle_set.add(norm)
        return kaggle_set

    def generate_candidates(
        self,
        canonical_symptoms_user: Set[str],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Generate disease candidates using weighted Jaccard similarity.

        Args:
            canonical_symptoms_user: Set of canonical Turkish symptom names.
            top_k: Override for max candidates to return.

        Returns:
            List of dicts: [{"disease_label", "score_0_1", "matched_symptoms", "missing_symptoms"}, ...]
        """
        if not self._loaded:
            logger.warning("CandidateGenerator not loaded, returning empty")
            return []

        if not canonical_symptoms_user:
            return []

        top_k = top_k or self._config.get("top_k", 5)
        min_score = self._config.get("min_score_to_include", 0.05)

        # Convert user canonicals to Kaggle space
        user_kaggle = self._canonical_to_kaggle_set(canonical_symptoms_user)
        if not user_kaggle:
            logger.info("No Kaggle symptoms mapped from user canonicals")
            return []

        results = []
        for disease, disease_symptoms_list in self._disease_symptoms.items():
            disease_set = set(disease_symptoms_list)

            intersection = user_kaggle & disease_set
            union = user_kaggle | disease_set

            if not union:
                continue

            # Weighted Jaccard
            numerator = sum(self._get_weight(s) for s in intersection)
            denominator = sum(self._get_weight(s) for s in union)

            score = numerator / denominator if denominator > 0 else 0.0

            if score >= min_score:
                results.append({
                    "disease_label": disease,
                    "score_0_1": round(score, 4),
                    "matched_symptoms": sorted(intersection),
                    "missing_symptoms": sorted(disease_set - user_kaggle),
                })

        # Sort: score desc, then disease_label asc (deterministic tie-break)
        results.sort(key=lambda x: (-x["score_0_1"], x["disease_label"]))

        return results[:top_k]

    def get_disease_symptoms(self, disease_label: str) -> List[str]:
        """Get all symptoms for a disease."""
        return self._disease_symptoms.get(disease_label, [])


# Singleton
candidate_generator = CandidateGenerator()
