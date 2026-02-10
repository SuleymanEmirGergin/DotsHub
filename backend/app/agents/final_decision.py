"""Final Decision Engine: Merge Layer A (disease candidates) + Layer B (rules scorer).

Produces a unified specialty ranking by combining:
- rules_score: from the deterministic specialty scorer (Layer B)
- specialty_prior_score: derived from disease candidate rankings (Layer A)

Tie-breaking is deterministic:
1) final_score descending
2) rules keyword_score descending
3) specialty_id alphabetical ascending
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ─── Paths ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(path: Path) -> dict:
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Prior points by disease candidate rank (rank 1 = most likely)
PRIOR_POINTS = {1: 4, 2: 3, 3: 2, 4: 1, 5: 1}


class FinalDecisionEngine:
    """Merges rules-based specialty scores with disease-candidate-based priors."""

    def __init__(self):
        self._disease_to_specialty: Dict[str, Dict] = {}
        self._fallback_specialty_id: str = "internal_gi"
        self._load()

    def _load(self):
        """Load disease-to-specialty mapping."""
        data = _load_json(_DATA_DIR / "disease_to_specialty.json")
        if not data:
            logger.warning("FinalDecisionEngine: disease_to_specialty.json not loaded")
            return

        self._fallback_specialty_id = data.get("fallback_specialty_id", "internal_gi")

        for entry in data.get("map", []):
            self._disease_to_specialty[entry["disease_label"]] = {
                "specialty_id": entry["specialty_id"],
                "specialty_tr": entry.get("specialty_tr", ""),
                "confidence": entry.get("confidence", 0.7),
            }

        logger.info(f"FinalDecisionEngine loaded: {len(self._disease_to_specialty)} disease mappings")

    def compute_specialty_priors(
        self, disease_candidates: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute specialty prior scores from disease candidate rankings.

        Args:
            disease_candidates: Ranked list from CandidateGenerator.
                Each: {"disease_label": str, "score_0_1": float, ...}

        Returns:
            Dict of specialty_id -> prior_score
        """
        priors: Dict[str, float] = {}

        for rank, candidate in enumerate(disease_candidates, 1):
            disease_label = candidate["disease_label"]
            mapping = self._disease_to_specialty.get(disease_label)

            if mapping is None:
                # Unknown disease -> use fallback
                specialty_id = self._fallback_specialty_id
                confidence = 0.5
            else:
                specialty_id = mapping["specialty_id"]
                confidence = mapping["confidence"]

            points = PRIOR_POINTS.get(rank, 0)
            prior_value = points * confidence

            if specialty_id not in priors:
                priors[specialty_id] = 0.0
            priors[specialty_id] += prior_value

        return priors

    def compute_final_scores(
        self,
        rules_scores: Dict[str, Dict],
        disease_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Dict]:
        """Merge Layer A + Layer B into final specialty scores.

        Args:
            rules_scores: From specialty_scorer.scores_to_dict()
                {specialty_id: {"score": float, "keyword_score": float, ...}}
            disease_candidates: From candidate_generator.generate_candidates()

        Returns:
            Dict of specialty_id -> {
                "final_score": float,
                "rules_score": float,
                "prior_score": float,
                "keyword_score": float,
                "specialty_tr": str
            }
        """
        # Step 1: Get priors from disease candidates
        priors = self.compute_specialty_priors(disease_candidates)

        # Step 2: Collect all specialty IDs
        all_ids = set(rules_scores.keys()) | set(priors.keys())

        # Step 3: Merge
        final: Dict[str, Dict] = {}
        for sid in all_ids:
            rules_entry = rules_scores.get(sid, {})
            rules_score = rules_entry.get("score", 0.0)
            keyword_score = rules_entry.get("keyword_score", 0.0)
            specialty_tr = rules_entry.get("name_tr", sid)

            prior_score = priors.get(sid, 0.0)

            # If we have a specialty_tr from the disease mapping, use it as fallback
            if specialty_tr == sid and disease_candidates:
                for candidate in disease_candidates:
                    mapping = self._disease_to_specialty.get(candidate["disease_label"])
                    if mapping and mapping["specialty_id"] == sid:
                        specialty_tr = mapping["specialty_tr"]
                        break

            final[sid] = {
                "final_score": round(rules_score + prior_score, 2),
                "rules_score": round(rules_score, 2),
                "prior_score": round(prior_score, 2),
                "keyword_score": round(keyword_score, 2),
                "specialty_tr": specialty_tr,
            }

        return final

    def get_top_specialty(
        self, final_scores: Dict[str, Dict]
    ) -> Optional[Dict[str, Any]]:
        """Get the winning specialty with deterministic tie-breaking.

        Tie-break order:
        1) final_score descending
        2) keyword_score descending (rules keyword matches)
        3) specialty_id alphabetical ascending
        """
        if not final_scores:
            return None

        sorted_entries = sorted(
            final_scores.items(),
            key=lambda x: (
                -x[1]["final_score"],
                -x[1]["keyword_score"],
                x[0],  # specialty_id alphabetical
            ),
        )

        top_id, top_data = sorted_entries[0]
        return {
            "id": top_id,
            "final_score": top_data["final_score"],
            "rules_score": top_data["rules_score"],
            "prior_score": top_data["prior_score"],
            "specialty_tr": top_data["specialty_tr"],
        }

    def get_ranked_specialties(
        self, final_scores: Dict[str, Dict], top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """Get ranked list of specialties."""
        sorted_entries = sorted(
            final_scores.items(),
            key=lambda x: (
                -x[1]["final_score"],
                -x[1]["keyword_score"],
                x[0],
            ),
        )

        return [
            {"id": sid, **data}
            for sid, data in sorted_entries[:top_n]
        ]


# Singleton
final_decision_engine = FinalDecisionEngine()
