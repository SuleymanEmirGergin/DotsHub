"""Stop Condition Engine - decides when to stop asking and start reasoning."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ─── Load stop conditions ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def _load_stop_conditions() -> dict:
    with open(_DATA_DIR / "stop_conditions.json", "r", encoding="utf-8") as f:
        return json.load(f)

_config = _load_stop_conditions()
_limits = _config["limits"]


class StopConditionStatus:
    """Tracks all stop condition fields for a session."""

    def __init__(self):
        self.chief_complaint_present: bool = False
        self.onset_or_duration_present: bool = False
        self.severity_estimated: bool = False
        self.negatives_checked_count: int = 0
        self.dominant_specialty_score: int = 0

    @property
    def at_least_one_negative_red_flag_checked(self) -> bool:
        return self.negatives_checked_count >= 1

    @property
    def at_least_two_negative_red_flags_checked(self) -> bool:
        return self.negatives_checked_count >= 2

    def to_dict(self) -> dict:
        return {
            "chief_complaint_present": self.chief_complaint_present,
            "onset_or_duration_present": self.onset_or_duration_present,
            "severity_estimated": self.severity_estimated,
            "at_least_one_negative_red_flag_checked": self.at_least_one_negative_red_flag_checked,
            "at_least_two_negative_red_flags_checked": self.at_least_two_negative_red_flags_checked,
            "dominant_specialty_score_gte_8": self.dominant_specialty_score >= 8,
            "dominant_specialty_score_gte_10": self.dominant_specialty_score >= 10,
            "sufficient_info": self.is_sufficient(),
        }

    def is_sufficient(self) -> bool:
        """Check if we have sufficient info using sufficiency rules."""
        # Low risk sufficient: all required + dominant score >= 8
        low_risk_ok = (
            self.chief_complaint_present
            and self.onset_or_duration_present
            and self.severity_estimated
            and self.at_least_one_negative_red_flag_checked
            and self.dominant_specialty_score >= 8
        )
        if low_risk_ok:
            return True

        # Medium risk sufficient: stricter
        medium_risk_ok = (
            self.chief_complaint_present
            and self.onset_or_duration_present
            and self.severity_estimated
            and self.at_least_two_negative_red_flags_checked
            and self.dominant_specialty_score >= 10
        )
        return medium_risk_ok


class StopConditionEngine:
    """Evaluates whether to stop asking questions and proceed to reasoning."""

    def __init__(self):
        self.max_questions = _limits["max_questions_total"]
        self.max_no_signal_rounds = _limits["max_rounds_without_new_signal"]
        self.time_limit_seconds = _limits["time_limit_seconds"]

    def should_stop(
        self,
        status: StopConditionStatus,
        questions_asked: int,
        rounds_without_new_signal: int,
        elapsed_seconds: float,
    ) -> tuple:
        """Determine if we should stop asking and proceed to reasoning.

        Returns:
            (should_stop: bool, reason: str, low_confidence: bool)
        """
        # ── Sufficiency check (best case: enough info) ──
        if status.is_sufficient():
            return (True, "sufficient_info", False)

        # ── Question limit ──
        if questions_asked >= self.max_questions:
            return (True, "max_questions_reached", True)

        # ── Time limit ──
        if elapsed_seconds >= self.time_limit_seconds:
            return (True, "time_limit_reached", True)

        # ── No new signal ──
        if rounds_without_new_signal >= self.max_no_signal_rounds:
            return (True, "no_new_signal", True)

        return (False, "", False)

    def detect_new_signal(
        self,
        prev_symptom_count: int,
        curr_symptom_count: int,
        prev_negatives_count: int,
        curr_negatives_count: int,
        prev_top_specialty_id: Optional[str],
        curr_top_specialty_id: Optional[str],
        prev_top_score: int,
        curr_top_score: int,
        prev_has_onset: bool,
        curr_has_onset: bool,
        prev_has_severity: bool,
        curr_has_severity: bool,
    ) -> bool:
        """Detect if a new signal was received from the latest user answer.

        A "new signal" is any of:
        - New symptom added
        - New critical attribute (onset/duration/severity)
        - New negative red-flag confirmed
        - Specialty score ranking changed (top1 changed or score increased by 5+)
        """
        if curr_symptom_count > prev_symptom_count:
            return True
        if curr_negatives_count > prev_negatives_count:
            return True
        if prev_top_specialty_id != curr_top_specialty_id:
            return True
        if curr_top_score >= prev_top_score + 5:
            return True
        if not prev_has_onset and curr_has_onset:
            return True
        if not prev_has_severity and curr_has_severity:
            return True

        return False

    def update_status_from_symptoms(
        self,
        status: StopConditionStatus,
        structured_symptoms: Optional[dict],
        negatives_checked: dict,
        top_specialty_score: int,
    ) -> StopConditionStatus:
        """Update stop condition status from current session state."""
        if structured_symptoms:
            syms = structured_symptoms
            # Chief complaint
            cc = syms.get("chief_complaint_tr") or syms.get("chief_complaint", "")
            status.chief_complaint_present = bool(cc and len(cc) > 2)

            # Onset/duration
            symptoms_list = syms.get("symptoms", [])
            for s in symptoms_list:
                onset = s.get("onset_tr") or s.get("onset")
                duration = s.get("duration_tr") or s.get("duration")
                if onset or duration:
                    status.onset_or_duration_present = True
                    break

            # Severity
            for s in symptoms_list:
                sev = s.get("severity_0_10")
                if sev is not None and sev > 0:
                    status.severity_estimated = True
                    break
            # Also mark if any symptom has severity-indicating notes
            if not status.severity_estimated:
                for s in symptoms_list:
                    notes = (s.get("notes_tr") or s.get("notes") or "").lower()
                    if any(w in notes for w in ["şiddetli", "hafif", "orta", "çok", "az"]):
                        status.severity_estimated = True
                        break

        # Negatives checked
        status.negatives_checked_count = sum(1 for v in negatives_checked.values() if v)

        # Dominant specialty score
        status.dominant_specialty_score = top_specialty_score

        return status


# Singleton
stop_condition_engine = StopConditionEngine()
