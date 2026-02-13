"""Orchestrator V4 - Unified Triage Turn (single endpoint, single envelope).

Frontend calls POST /v1/triage/turn → gets one Envelope back.
type field determines what to render: QUESTION | RESULT | EMERGENCY | ERROR.

Flow:
1. Safety Guard (every message) - rules.json powered
2. Symptom Interpreter (first message only)
3. Rules Scorer (Layer B) - deterministic specialty scoring
4. Candidate Generator (Layer A) - weighted Jaccard disease candidates
5. Final Decision (A+B merge) - unified specialty ranking
6. Deterministic Stop Check (stop_rules.json)
7a. IF not stopped: Question Selector (deterministic) -> LLM fallback
7b. IF stopped: build deterministic RESULT payload
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

from app.agents.safety_guard import SafetyGuardAgent
from app.agents.symptom_interpreter import SymptomInterpreterAgent
from app.agents.question_generator import QuestionGeneratorAgent
from app.agents.reasoning_risk import ReasoningRiskAgent
from app.agents.medical_routing import MedicalRoutingAgent
from app.agents.specialty_scorer import specialty_scorer
from app.agents.stop_condition import stop_condition_engine, StopConditionStatus
from app.agents.candidate_generator import candidate_generator
from app.agents.final_decision import final_decision_engine
from app.agents.question_selector import question_selector
from app.models.schemas import (
    SafetyGuardOutput,
    InterpreterOutput,
    QuestionOutput,
    ReasoningOutput,
    RoutingOutput,
    UserProfile,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Load stop rules ───
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STOP_RULES: Dict[str, Any] = {}
try:
    with open(_DATA_DIR / "stop_rules.json", "r", encoding="utf-8") as f:
        _STOP_RULES = json.load(f)
except FileNotFoundError:
    logger.warning("stop_rules.json not found, using defaults")
    _STOP_RULES = {"max_questions": 6, "confidence_rules": {"high_confidence_disease_score": 0.45, "min_specialty_score_gap": 2.0}}


class OrchestratorResult:
    """Result from a single orchestrator step."""

    def __init__(
        self,
        action: str,  # "emergency", "question", "result"
        message: str = "",
        emergency: Optional[SafetyGuardOutput] = None,
        question: Optional[QuestionOutput] = None,
        reasoning: Optional[ReasoningOutput] = None,
        routing: Optional[RoutingOutput] = None,
        low_confidence: bool = False,
    ):
        self.action = action
        self.message = message
        self.emergency = emergency
        self.question = question
        self.reasoning = reasoning
        self.routing = routing
        self.low_confidence = low_confidence


class SessionState:
    """Enriched in-memory state for an active triage session."""

    def __init__(self, session_id: str, profile: Optional[UserProfile] = None):
        self.session_id = session_id
        self.profile = profile
        self.structured_symptoms: Optional[InterpreterOutput] = None
        self.conversation_history: List[Dict[str, str]] = []
        self.question_count: int = 0
        self.is_complete: bool = False
        self.reasoning_output: Optional[ReasoningOutput] = None
        self.routing_output: Optional[RoutingOutput] = None

        # V2 enriched fields
        self.specialty_scores: Dict[str, dict] = {}
        self.top_specialty: Optional[Dict[str, Any]] = None
        self.negatives_checked: Dict[str, bool] = {
            "stroke_like": False,
            "severe_breathing": False,
            "gi_bleeding": False,
            "self_harm": False,
            "cardiac": False,
        }
        self.rounds_without_new_signal: int = 0
        self.last_new_signal_at: Optional[datetime] = None
        self.start_time: float = time.time()
        self.stop_condition_status: StopConditionStatus = StopConditionStatus()
        self.low_confidence: bool = False

        # V3 deterministic pipeline fields
        self.disease_candidates: List[Dict[str, Any]] = []
        self.final_specialty_scores: Dict[str, Dict] = {}
        self.asked_symptoms: Set[str] = set()  # canonical symptoms already asked about
        self.known_symptoms: Set[str] = set()   # canonical symptoms confirmed present
        self.denied_symptoms: Set[str] = set()   # canonical symptoms confirmed absent

        # V4 unified turn fields
        self.turn_index: int = 0
        self.stop_reason: Optional[str] = None
        self.confidence: float = 0.0
        self._last_asked_canonical: Optional[str] = None  # tracks canonical of last question
        self.raw_texts: List[str] = []  # all user free-text messages
        self.answers: Dict[str, str] = {}  # canonical -> yes/no/value

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def get_canonical_symptoms_from_interpreter(self) -> Set[str]:
        """Extract canonical symptom names from the interpreter output."""
        if not self.structured_symptoms:
            return set()
        return {s.name_tr.lower().strip() for s in self.structured_symptoms.symptoms if s.name_tr}

    def to_context(self) -> dict:
        """Build context dict for agents."""
        ctx: dict = {
            "conversation_history": self.conversation_history,
            "question_count": self.question_count,
        }
        if self.structured_symptoms:
            ctx["structured_symptoms"] = self.structured_symptoms.model_dump()
        if self.profile:
            ctx["profile"] = self.profile.model_dump()
        if self.specialty_scores:
            ctx["specialty_scores"] = self.specialty_scores
        if self.top_specialty:
            ctx["top_specialty"] = self.top_specialty
        if self.disease_candidates:
            ctx["disease_candidates"] = self.disease_candidates
        if self.final_specialty_scores:
            ctx["final_specialty_scores"] = self.final_specialty_scores
        return ctx

    def to_state_dict(self) -> dict:
        """Full state snapshot for debug endpoint."""
        return {
            "session_id": self.session_id,
            "profile": self.profile.model_dump() if self.profile else None,
            "chat_history": self.conversation_history,
            "structured_symptoms": self.structured_symptoms.model_dump() if self.structured_symptoms else None,
            "negatives_checked": self.negatives_checked,
            "specialty_scores": self.specialty_scores,
            "top_specialty": self.top_specialty,
            "questions_asked": self.question_count,
            "rounds_without_new_signal": self.rounds_without_new_signal,
            "last_new_signal_at": str(self.last_new_signal_at) if self.last_new_signal_at else None,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "stop_condition_status": self.stop_condition_status.to_dict(),
            "is_complete": self.is_complete,
            "low_confidence": self.low_confidence,
            # V3 fields
            "disease_candidates": self.disease_candidates,
            "final_specialty_scores": self.final_specialty_scores,
            "asked_symptoms": sorted(self.asked_symptoms),
            "known_symptoms": sorted(self.known_symptoms),
            "denied_symptoms": sorted(self.denied_symptoms),
            # V4 unified turn fields
            "turn_index": self.turn_index,
            "stop_reason": self.stop_reason,
            "confidence": round(self.confidence, 3),
            "answers": self.answers,
        }


class Orchestrator:
    """V3 orchestrator with deterministic scoring pipeline (A+B).

    Flow:
    1. Safety Guard (every message) - rules.json powered
    2. Symptom Interpreter (first message)
    3. Rules Scorer (Layer B)
    4. Candidate Generator (Layer A)
    5. Final Decision (A+B merge)
    6. Stop Condition Check (uses final scores)
    7. Question Selector (deterministic) -> LLM fallback
    8. Reasoning & Risk + Medical Routing (when stopped)
    """

    def __init__(self):
        self.safety_guard = SafetyGuardAgent()
        self.symptom_interpreter = SymptomInterpreterAgent()
        self.question_generator = QuestionGeneratorAgent()
        self.reasoning_risk = ReasoningRiskAgent()
        self.medical_routing = MedicalRoutingAgent()
        self._sessions: Dict[str, SessionState] = {}

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def create_session(self, session_id: str, profile: Optional[UserProfile] = None) -> SessionState:
        state = SessionState(session_id, profile)
        self._sessions[session_id] = state
        return state

    def _update_negatives_from_conversation(self, state: SessionState):
        """Update negatives_checked based on conversation history."""
        full_text = " ".join(
            m["content"].lower() for m in state.conversation_history if m["role"] == "user"
        )
        neg_keywords = {
            "stroke_like": ["güçsüzlük yok", "konuşma bozukluğu yok", "uyuşma yok", "kayma yok"],
            "severe_breathing": ["nefes darlığı yok", "nefesim normal"],
            "gi_bleeding": ["kan yok", "kanlı değil", "siyah değil"],
            "self_harm": ["zarar yok", "intihar yok"],
            "cardiac": ["göğüs ağrısı yok", "baskı yok", "terleme yok"],
        }
        for key, keywords in neg_keywords.items():
            if any(kw in full_text for kw in keywords):
                state.negatives_checked[key] = True

        # Also check AI questions + user "hayır" answers
        for i, msg in enumerate(state.conversation_history):
            if msg["role"] == "user" and msg["content"].lower().strip() in ("hayır", "hayir", "yok", "olmadı"):
                if i > 0 and state.conversation_history[i - 1]["role"] == "ai":
                    q = state.conversation_history[i - 1]["content"].lower()
                    if any(w in q for w in ["güçsüzlük", "konuşma", "uyuşma", "kayma", "felç"]):
                        state.negatives_checked["stroke_like"] = True
                    if any(w in q for w in ["nefes", "boğul"]):
                        state.negatives_checked["severe_breathing"] = True
                    if any(w in q for w in ["kan", "siyah", "katran"]):
                        state.negatives_checked["gi_bleeding"] = True
                    if any(w in q for w in ["bayıl", "baskı", "terle"]):
                        state.negatives_checked["cardiac"] = True

    def _run_scorer(self, state: SessionState, text: str):
        """Run specialty scorer on new text, accumulating scores (Layer B)."""
        scores = specialty_scorer.score_text(text, state.specialty_scores)
        state.specialty_scores = specialty_scorer.scores_to_dict(scores)
        state.top_specialty = specialty_scorer.get_top_specialty(scores)

    def _run_candidate_generator(self, state: SessionState):
        """Run Layer A: disease candidate generation."""
        if not candidate_generator.is_loaded:
            logger.info("CandidateGenerator not loaded, skipping Layer A")
            return

        # Get canonical symptoms from interpreter + known symptoms
        canonical = state.get_canonical_symptoms_from_interpreter() | state.known_symptoms
        if not canonical:
            return

        state.disease_candidates = candidate_generator.generate_candidates(canonical)
        logger.info(
            f"[Orchestrator] Layer A: {len(state.disease_candidates)} candidates "
            f"from {len(canonical)} canonical symptoms"
        )

    def _run_final_decision(self, state: SessionState):
        """Run A+B merge: combine rules scores + disease priors."""
        state.final_specialty_scores = final_decision_engine.compute_final_scores(
            state.specialty_scores,
            state.disease_candidates,
        )
        # Update top_specialty from final scores
        final_top = final_decision_engine.get_top_specialty(state.final_specialty_scores)
        if final_top:
            state.top_specialty = final_top
            logger.info(
                f"[Orchestrator] Final Decision: top={final_top['id']} "
                f"(final={final_top['final_score']}, rules={final_top['rules_score']}, "
                f"prior={final_top['prior_score']})"
            )

    def _run_question_selector(self, state: SessionState) -> Optional[QuestionOutput]:
        """Run deterministic question selection. Returns QuestionOutput or None for LLM fallback."""
        result = question_selector.select_question(
            disease_candidates=state.disease_candidates,
            known_symptoms=state.known_symptoms | state.denied_symptoms,
            asked_symptoms=state.asked_symptoms,
        )

        if result is None:
            return None

        # Track the asked symptom
        state.asked_symptoms.add(result["canonical_symptom"])

        choices = result.get("choices_tr")
        if choices is None and result["answer_type"] == "yes_no":
            choices = ["Evet", "Hayır"]
        elif choices is None:
            choices = []
        return QuestionOutput(
            question_tr=result["question_tr"],
            answer_type=result["answer_type"],
            choices_tr=choices,
            why_this_question_tr=f"Ayırt edici soru: {result['canonical_symptom']}",
            stop=False,
        )

    def _update_known_symptoms_from_answer(self, state: SessionState, answer_text: str):
        """Update known/denied symptoms based on user's yes/no answer."""
        answer_lower = answer_text.lower().strip()

        # Check if the previous message was a question about a specific symptom
        if not state.conversation_history:
            return

        # Find the last asked symptom
        last_asked = None
        for sym in state.asked_symptoms:
            # The most recently asked symptom
            last_asked = sym

        if not last_asked:
            return

        # Determine if yes or no
        positive_answers = {"evet", "var", "oldu", "oluyor", "hissediyorum", "yes"}
        negative_answers = {"hayır", "hayir", "yok", "olmadı", "olmuyor", "hissetmiyorum", "no"}

        if answer_lower in positive_answers:
            state.known_symptoms.add(last_asked)
            logger.info(f"[Orchestrator] Symptom confirmed: {last_asked}")
        elif answer_lower in negative_answers:
            state.denied_symptoms.add(last_asked)
            logger.info(f"[Orchestrator] Symptom denied: {last_asked}")

    def _check_stop_condition(self, state: SessionState) -> tuple:
        """Check if we should stop asking. Returns (should_stop, reason, low_confidence)."""
        # Use final_score if available, otherwise raw rules_score
        top_score = 0
        if state.top_specialty:
            top_score = state.top_specialty.get("final_score", state.top_specialty.get("score", 0))

        stop_condition_engine.update_status_from_symptoms(
            state.stop_condition_status,
            state.structured_symptoms.model_dump() if state.structured_symptoms else None,
            state.negatives_checked,
            top_score,
        )
        return stop_condition_engine.should_stop(
            state.stop_condition_status,
            state.question_count,
            state.rounds_without_new_signal,
            state.elapsed_seconds,
        )

    async def handle_initial_symptoms(
        self,
        session_id: str,
        symptoms_text: str,
        profile: Optional[UserProfile] = None,
    ) -> OrchestratorResult:
        """Handle the first message: symptoms input."""
        state = self.create_session(session_id, profile)
        state.add_message("user", symptoms_text)

        # Step 1: Safety Guard
        safety_context = {
            "user_message": symptoms_text,
            "symptoms": [],
            "profile": profile.model_dump() if profile else {},
        }
        safety_result = await self.safety_guard.run(safety_context)

        if safety_result.status == "EMERGENCY":
            state.is_complete = True
            return OrchestratorResult(
                action="emergency",
                message=self._format_emergency_message(safety_result),
                emergency=safety_result,
            )

        # Step 2: Interpret symptoms
        interpreter_context = {
            "user_message": symptoms_text,
            "profile": profile.model_dump() if profile else {},
        }
        state.structured_symptoms = await self.symptom_interpreter.run(interpreter_context)

        # Merge profile
        if profile:
            ctx = state.structured_symptoms.context
            if not ctx.age and profile.age:
                ctx.age = profile.age
            if not ctx.sex and profile.sex:
                ctx.sex = profile.sex
            if profile.chronic_conditions:
                ctx.chronic_conditions_tr = list(set(ctx.chronic_conditions_tr + profile.chronic_conditions))

        # Initialize known symptoms from interpreter
        state.known_symptoms = state.get_canonical_symptoms_from_interpreter()

        # Step 3: Rules Scorer (Layer B)
        self._run_scorer(state, symptoms_text)
        state.last_new_signal_at = datetime.now(timezone.utc)

        # Step 4: Candidate Generator (Layer A)
        self._run_candidate_generator(state)

        # Step 5: Final Decision (A+B merge)
        self._run_final_decision(state)

        # Step 6: Check stop condition
        should_stop, reason, low_confidence = self._check_stop_condition(state)
        if should_stop:
            state.low_confidence = low_confidence
            return await self._finalize(state)

        # Step 7: Question selection (deterministic first, LLM fallback)
        question_result = self._run_question_selector(state)

        if question_result is None:
            # LLM fallback
            logger.info("[Orchestrator] Deterministic question selector returned None, using LLM fallback")
            question_context = state.to_context()
            question_result = await self.question_generator.run(question_context)

            if question_result.stop:
                return await self._finalize(state)

        state.question_count += 1
        state.add_message("ai", question_result.question_tr)

        return OrchestratorResult(
            action="question",
            message=question_result.question_tr,
            question=question_result,
        )

    async def handle_user_answer(
        self,
        session_id: str,
        answer_text: str,
    ) -> OrchestratorResult:
        """Handle a user's answer to a question."""
        state = self.get_session(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        if state.is_complete:
            raise ValueError(f"Session {session_id} is already complete")

        # Snapshot for signal detection
        prev_symptom_count = len(state.structured_symptoms.symptoms) if state.structured_symptoms else 0
        prev_neg_count = sum(1 for v in state.negatives_checked.values() if v)
        prev_top_id = state.top_specialty["id"] if state.top_specialty else None
        prev_top_score = state.top_specialty.get("final_score", state.top_specialty.get("score", 0)) if state.top_specialty else 0
        prev_has_onset = state.stop_condition_status.onset_or_duration_present
        prev_has_severity = state.stop_condition_status.severity_estimated

        state.add_message("user", answer_text)

        # Step 1: Safety Guard
        safety_context = {
            "user_message": answer_text,
            "symptoms": [s.model_dump() for s in state.structured_symptoms.symptoms] if state.structured_symptoms else [],
            "profile": state.profile.model_dump() if state.profile else {},
            "conversation_history": state.conversation_history,
        }
        safety_result = await self.safety_guard.run(safety_context)

        if safety_result.status == "EMERGENCY":
            state.is_complete = True
            return OrchestratorResult(
                action="emergency",
                message=self._format_emergency_message(safety_result),
                emergency=safety_result,
            )

        # Step 2: Update negatives from conversation
        self._update_negatives_from_conversation(state)

        # Update known/denied symptoms from answer
        self._update_known_symptoms_from_answer(state, answer_text)

        # Step 3: Rules Scorer (Layer B) on new answer
        self._run_scorer(state, answer_text)

        # Step 4: Candidate Generator (Layer A) with updated symptoms
        self._run_candidate_generator(state)

        # Step 5: Final Decision (A+B merge)
        self._run_final_decision(state)

        # Step 6: Signal detection
        curr_symptom_count = len(state.structured_symptoms.symptoms) if state.structured_symptoms else 0
        curr_neg_count = sum(1 for v in state.negatives_checked.values() if v)
        curr_top_id = state.top_specialty["id"] if state.top_specialty else None
        curr_top_score = state.top_specialty.get("final_score", state.top_specialty.get("score", 0)) if state.top_specialty else 0

        # Update stop condition status first
        self._check_stop_condition(state)
        curr_has_onset = state.stop_condition_status.onset_or_duration_present
        curr_has_severity = state.stop_condition_status.severity_estimated

        has_new_signal = stop_condition_engine.detect_new_signal(
            prev_symptom_count, curr_symptom_count,
            prev_neg_count, curr_neg_count,
            prev_top_id, curr_top_id,
            prev_top_score, curr_top_score,
            prev_has_onset, curr_has_onset,
            prev_has_severity, curr_has_severity,
        )

        if has_new_signal:
            state.rounds_without_new_signal = 0
            state.last_new_signal_at = datetime.now(timezone.utc)
        else:
            state.rounds_without_new_signal += 1

        # Step 7: Check stop condition
        should_stop, reason, low_confidence = self._check_stop_condition(state)
        if should_stop:
            state.low_confidence = low_confidence
            return await self._finalize(state)

        # Step 8: Question selection (deterministic first, LLM fallback)
        question_result = self._run_question_selector(state)

        if question_result is None:
            # LLM fallback
            logger.info("[Orchestrator] Deterministic question selector returned None, using LLM fallback")
            question_context = state.to_context()
            question_result = await self.question_generator.run(question_context)

            if question_result.stop:
                return await self._finalize(state)

        state.question_count += 1
        state.add_message("ai", question_result.question_tr)

        return OrchestratorResult(
            action="question",
            message=question_result.question_tr,
            question=question_result,
        )

    # ─── V4: Unified Triage Turn ───

    def _should_stop_v4(self, state: SessionState) -> bool:
        """Deterministic stop check using stop_rules.json. Sets state.stop_reason."""
        max_q = _STOP_RULES.get("max_questions", 6)
        conf = _STOP_RULES.get("confidence_rules", {})
        high_disease = conf.get("high_confidence_disease_score", 0.45)
        min_gap = conf.get("min_specialty_score_gap", 2.0)

        # Hard: max questions
        if state.turn_index >= max_q:
            state.stop_reason = "MAX_QUESTIONS_REACHED"
            state.low_confidence = True
            return True

        # Soft: high confidence single disease
        if state.disease_candidates:
            top_score = state.disease_candidates[0].get("score_0_1", 0)
            if top_score >= high_disease:
                state.stop_reason = "HIGH_CONFIDENCE_SINGLE_DISEASE"
                return True

        # Soft: clear specialty winner (gap between top two)
        if state.final_specialty_scores:
            ranked = final_decision_engine.get_ranked_specialties(state.final_specialty_scores, top_n=2)
            if len(ranked) >= 2:
                gap = ranked[0]["final_score"] - ranked[1]["final_score"]
                if gap >= min_gap:
                    state.stop_reason = "CLEAR_SPECIALTY_WINNER"
                    return True

        return False

    def _compute_confidence(self, state: SessionState) -> float:
        """Compute a 0-1 confidence score from the current state."""
        top1 = state.disease_candidates[0]["score_0_1"] if state.disease_candidates else 0
        top2 = state.disease_candidates[1]["score_0_1"] if len(state.disease_candidates) > 1 else 0
        gap = max(0, top1 - top2)
        confidence = min(1.0, max(0.0, (top1 * 0.75) + (gap * 0.6)))
        return round(confidence, 3)

    def _build_result_payload(self, state: SessionState) -> dict:
        """Build deterministic RESULT payload — no LLM needed."""
        # Summary lines
        summary = []
        for c in sorted(state.known_symptoms):
            summary.append(f"{c.capitalize()} mevcut.")
        for k, v in sorted(state.answers.items()):
            if k not in state.known_symptoms:
                label = "var" if v.lower() in ("yes", "evet", "var") else "yok"
                summary.append(f"{k.capitalize()}: {label}.")

        # Safety notes
        safety_notes = [
            "Bu bir ön değerlendirmedir, tıbbi teşhis değildir.",
            "Şikayetler artarsa veya yeni belirtiler eklenirse doktora başvur.",
        ]
        top_id = state.top_specialty.get("id", "") if state.top_specialty else ""
        if top_id in ("neurology", "cardiology"):
            safety_notes.append(
                "Ani bilinç kaybı, konuşma bozukluğu veya şiddetli ağrı durumunda acile başvur."
            )

        # Urgency
        urgency = "ROUTINE"
        if state.disease_candidates:
            top_disease = state.disease_candidates[0]["disease_label"]
            if "Heart attack" in top_disease or "Paralysis" in top_disease:
                urgency = "SAME_DAY"

        # Top conditions
        top_conditions = []
        for d in state.disease_candidates[:3]:
            top_conditions.append({
                "disease_label": d["disease_label"],
                "score_0_1": round(d["score_0_1"], 2),
            })

        # Recommended specialty
        spec_id = top_id or "internal_gi"
        spec_tr = state.top_specialty.get("specialty_tr", "Dahiliye") if state.top_specialty else "Dahiliye"

        return {
            "urgency": urgency,
            "recommended_specialty": {"id": spec_id, "name_tr": spec_tr},
            "top_conditions": top_conditions,
            "doctor_ready_summary_tr": summary,
            "safety_notes_tr": safety_notes,
        }

    async def handle_turn(
        self,
        session_id: Optional[str],
        user_message: str,
        answer_canonical: Optional[str] = None,
        answer_value: Optional[str] = None,
    ) -> dict:
        """Unified triage turn handler — single entry point.

        Returns a dict ready to be wrapped in an Envelope:
        {"type": "QUESTION"|"RESULT"|"EMERGENCY"|"ERROR", "session_id": str, "turn_index": int, "payload": dict}
        """
        # ── Session init or resume ──
        is_new = session_id is None or self.get_session(session_id) is None
        if is_new:
            session_id = session_id or str(uuid.uuid4())
            state = self.create_session(session_id)
        else:
            state = self.get_session(session_id)
            if state.is_complete:
                return {
                    "type": "ERROR",
                    "session_id": session_id,
                    "turn_index": state.turn_index,
                    "payload": {"code": "SESSION_COMPLETE", "message_tr": "Bu oturum zaten tamamlandı."},
                }

        state.turn_index += 1

        # ── Apply incoming data ──
        if user_message and user_message.strip():
            state.raw_texts.append(user_message.strip())
            state.add_message("user", user_message.strip())

        if answer_canonical and answer_value is not None:
            state.answers[answer_canonical] = answer_value
            state.asked_symptoms.add(answer_canonical)
            state._last_asked_canonical = None
            # Update known/denied
            if answer_value.lower() in ("yes", "evet", "var"):
                state.known_symptoms.add(answer_canonical)
            elif answer_value.lower() in ("no", "hayır", "hayir", "yok"):
                state.denied_symptoms.add(answer_canonical)
            if not user_message.strip():
                state.add_message("user", f"{answer_canonical}: {answer_value}")

        # ── 1. Safety Guard ──
        all_text = " ".join(state.raw_texts)
        safety_context = {
            "user_message": all_text,
            "symptoms": [s.model_dump() for s in state.structured_symptoms.symptoms] if state.structured_symptoms else [],
            "profile": state.profile.model_dump() if state.profile else {},
        }
        safety_result = await self.safety_guard.run(safety_context)

        if safety_result.status == "EMERGENCY":
            state.is_complete = True
            return {
                "type": "EMERGENCY",
                "session_id": session_id,
                "turn_index": state.turn_index,
                "payload": {
                    "urgency": "EMERGENCY",
                    "reason_tr": safety_result.reason,
                    "instructions_tr": safety_result.emergency_instructions,
                },
            }

        # ── 2. Interpret symptoms (first time or when new free-text arrives) ──
        if is_new or (user_message and user_message.strip()):
            interpreter_context = {
                "user_message": all_text,
                "profile": state.profile.model_dump() if state.profile else {},
            }
            state.structured_symptoms = await self.symptom_interpreter.run(interpreter_context)
            state.known_symptoms |= state.get_canonical_symptoms_from_interpreter()

        # ── 3. Layer B: Rules scorer ──
        if user_message and user_message.strip():
            self._run_scorer(state, user_message)
        if answer_canonical and answer_value and answer_value.lower() in ("yes", "evet", "var"):
            self._run_scorer(state, answer_canonical)

        # ── 4. Layer A: Candidate generator ──
        self._run_candidate_generator(state)

        # ── 5. Final decision (A+B merge) ──
        self._run_final_decision(state)

        # ── 6. Compute confidence ──
        state.confidence = self._compute_confidence(state)

        # ── 7. Stop check ──
        should_stop = self._should_stop_v4(state)

        # Also check: no discriminative question available
        if not should_stop:
            next_q = self._run_question_selector(state)
            if next_q is None:
                # Try LLM fallback... but if we don't want LLM, mark stop
                state.stop_reason = "NO_MORE_DISCRIMINATIVE_QUESTIONS"
                should_stop = True
        else:
            next_q = None

        # ── RESULT branch ──
        if should_stop:
            state.is_complete = True
            payload = self._build_result_payload(state)
            return {
                "type": "RESULT",
                "session_id": session_id,
                "turn_index": state.turn_index,
                "payload": payload,
            }

        # ── QUESTION branch ──
        state.question_count += 1
        canonical = next_q.question_tr.split(":")[0] if ":" in next_q.question_tr else ""
        # Get canonical from the question output's why field
        q_canonical = ""
        if next_q.why_this_question_tr and ":" in next_q.why_this_question_tr:
            q_canonical = next_q.why_this_question_tr.split(":")[-1].strip()

        # Find canonical from asked_symptoms (last added)
        if not q_canonical:
            for sym in state.asked_symptoms:
                q_canonical = sym  # last one added

        state._last_asked_canonical = q_canonical
        state.add_message("ai", next_q.question_tr)

        return {
            "type": "QUESTION",
            "session_id": session_id,
            "turn_index": state.turn_index,
            "payload": {
                "question_id": f"q_{state.question_count:03d}",
                "canonical": q_canonical,
                "question_tr": next_q.question_tr,
                "answer_type": next_q.answer_type,
                "choices_tr": next_q.choices_tr if next_q.choices_tr else (
                    ["yes", "no"] if next_q.answer_type == "yes_no" else None
                ),
                "why_asking_tr": next_q.why_this_question_tr or None,
            },
        }

    async def _finalize(self, state: SessionState) -> OrchestratorResult:
        """Run final analysis: Reasoning + Routing."""
        logger.info(f"[Orchestrator] Finalizing session {state.session_id} (low_confidence={state.low_confidence})")

        # Reasoning & Risk
        reasoning_context = state.to_context()
        state.reasoning_output = await self.reasoning_risk.run(reasoning_context)

        # Medical Routing (with final specialty scores for alignment)
        routing_context = {
            **state.to_context(),
            "reasoning_output": state.reasoning_output.model_dump(),
        }
        state.routing_output = await self.medical_routing.run(routing_context)

        state.is_complete = True
        message = self._format_result_message(state.reasoning_output, state.routing_output)

        return OrchestratorResult(
            action="result",
            message=message,
            reasoning=state.reasoning_output,
            routing=state.routing_output,
            low_confidence=state.low_confidence,
        )

    def _format_emergency_message(self, emergency: SafetyGuardOutput) -> str:
        lines = ["ACİL DURUM UYARISI\n"]
        if emergency.reason:
            lines.append(emergency.reason)
        lines.append("")
        for instruction in emergency.emergency_instructions:
            lines.append(f"• {instruction}")
        return "\n".join(lines)

    def _format_result_message(self, reasoning: ReasoningOutput, routing: RoutingOutput) -> str:
        lines = []
        lines.append("Olası Durumlar:\n")
        for c in reasoning.candidates:
            pct = int(c.probability_0_1 * 100)
            lines.append(f"  %{pct} - {c.label_tr}")

        lines.append(f"\nÖnerilen Branş: {routing.recommended_specialty_tr}")

        urgency_map = {
            "ER_NOW": "Hemen Acil",
            "SAME_DAY": "Bugün İçinde",
            "WITHIN_3_DAYS": "1–3 Gün İçinde",
            "ROUTINE": "Rutin",
        }
        lines.append(f"Aciliyet: {urgency_map.get(routing.urgency, routing.urgency)}")

        if routing.emergency_watchouts_tr:
            lines.append("\nŞu belirtiler gelişirse acile gidin:")
            for w in routing.emergency_watchouts_tr:
                lines.append(f"  • {w}")

        return "\n".join(lines)


# Singleton
orchestrator = Orchestrator()
