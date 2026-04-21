"""Unit tests for the pure / deterministic helpers of Orchestrator V4.

Scope & non-scope
-----------------
The orchestrator is a big class (~540 executable statements) that glues
together safety_guard → symptom_interpreter → scorer → candidate_generator
→ final_decision → stop_condition → question_selector. End-to-end coverage
lives in `tests/test_golden_flows.py`. This file, by contrast, targets
the **deterministic, LLM-independent** helpers so a regression on a data
shape or a branch condition shows up as a unit failure instead of a
mysterious golden-flow diff.

Covered helpers
---------------
- `OrchestratorResult.__init__` — result-envelope container shape.
- `SessionState.__init__` + field defaults / per-instance mutability.
- `SessionState.add_message`
- `SessionState.elapsed_seconds` (property)
- `SessionState.get_canonical_symptoms_from_interpreter`
- `SessionState.to_context` (conditional fields)
- `SessionState.to_state_dict` (full snapshot)
- `Orchestrator.get_session` / `create_session` (session registry)
- `Orchestrator._update_negatives_from_conversation` (keyword + Q/A paths)
- `Orchestrator._update_known_symptoms_from_answer` (yes/no/other)
- `Orchestrator._compute_confidence` (math: top1 * 0.75 + gap * 0.6)
- `Orchestrator._should_stop_v4` — MAX_QUESTIONS / HIGH_CONFIDENCE /
  CLEAR_SPECIALTY_WINNER branches
- `Orchestrator._build_doctor_summary_sentence`
- `Orchestrator._build_result_payload` — urgency + top_conditions + shape
- `Orchestrator._format_emergency_message`
- `Orchestrator._format_result_message` — urgency map + watchouts branch
"""

from __future__ import annotations

import time
import unittest

from app.agents.orchestrator import (
    Orchestrator,
    OrchestratorResult,
    SessionState,
)
from app.models.schemas import (
    CandidateCondition,
    InterpreterOutput,
    ReasoningOutput,
    RoutingOutput,
    SafetyGuardOutput,
    SymptomItem,
    UserProfile,
)


# ─── OrchestratorResult ───────────────────────────────────────────────


class OrchestratorResultTests(unittest.TestCase):
    """Container for a single turn's outcome. A regression that swapped
    default fields would silently break downstream dispatchers that read
    `.question` / `.emergency`."""

    def test_defaults_are_all_none_or_empty(self):
        r = OrchestratorResult(action="question")
        self.assertEqual(r.action, "question")
        self.assertEqual(r.message, "")
        self.assertIsNone(r.emergency)
        self.assertIsNone(r.question)
        self.assertIsNone(r.reasoning)
        self.assertIsNone(r.routing)
        self.assertFalse(r.low_confidence)

    def test_custom_emergency_result(self):
        emerg = SafetyGuardOutput(
            status="EMERGENCY", reason="GOGUS_AGRI", emergency_instructions=["Ara 112"]
        )
        r = OrchestratorResult(action="emergency", emergency=emerg, message="!!!")
        self.assertEqual(r.action, "emergency")
        self.assertEqual(r.message, "!!!")
        self.assertIs(r.emergency, emerg)

    def test_low_confidence_flag_propagates(self):
        r = OrchestratorResult(action="result", low_confidence=True)
        self.assertTrue(r.low_confidence)


# ─── SessionState ─────────────────────────────────────────────────────


class SessionStateDefaultsTests(unittest.TestCase):
    def test_fresh_state_has_session_id_and_empty_collections(self):
        state = SessionState("sess-1")
        self.assertEqual(state.session_id, "sess-1")
        self.assertIsNone(state.profile)
        self.assertIsNone(state.structured_symptoms)
        self.assertEqual(state.conversation_history, [])
        self.assertEqual(state.question_count, 0)
        self.assertFalse(state.is_complete)
        self.assertEqual(state.specialty_scores, {})
        self.assertIsNone(state.top_specialty)
        self.assertEqual(state.asked_symptoms, set())
        self.assertEqual(state.known_symptoms, set())
        self.assertEqual(state.denied_symptoms, set())
        self.assertEqual(state.raw_texts, [])
        self.assertEqual(state.answers, {})
        self.assertEqual(state.locale, "tr-TR")
        # All red-flag categories start unchecked.
        for key in (
            "stroke_like",
            "severe_breathing",
            "gi_bleeding",
            "self_harm",
            "cardiac",
        ):
            self.assertFalse(state.negatives_checked[key])

    def test_two_states_dont_share_mutable_defaults(self):
        # Regression guard: if any List/Dict/Set default gets written as
        # a class attribute, two sessions would leak into each other.
        a = SessionState("A")
        b = SessionState("B")
        a.known_symptoms.add("baş ağrısı")
        a.conversation_history.append({"role": "user", "content": "x"})
        a.answers["q"] = "yes"
        self.assertNotIn("baş ağrısı", b.known_symptoms)
        self.assertEqual(b.conversation_history, [])
        self.assertEqual(b.answers, {})

    def test_profile_is_stored_by_reference(self):
        p = UserProfile(age=42, sex="F")
        state = SessionState("s", profile=p)
        self.assertIs(state.profile, p)

    def test_elapsed_seconds_returns_positive_float_after_sleep(self):
        state = SessionState("s")
        # Force a known epoch in the past; we're just verifying the
        # property subtracts from now(), not actually timing anything.
        state.start_time = time.time() - 1.0
        self.assertGreaterEqual(state.elapsed_seconds, 1.0)


class SessionStateMutatorTests(unittest.TestCase):
    def test_add_message_appends_in_order(self):
        state = SessionState("s")
        state.add_message("user", "başım ağrıyor")
        state.add_message("ai", "Ne zaman başladı?")
        state.add_message("user", "3 gündür")
        self.assertEqual(len(state.conversation_history), 3)
        self.assertEqual(state.conversation_history[0]["role"], "user")
        self.assertEqual(state.conversation_history[1]["role"], "ai")
        self.assertEqual(
            state.conversation_history[2]["content"], "3 gündür"
        )

    def test_get_canonical_symptoms_returns_empty_set_when_no_interpreter(self):
        state = SessionState("s")
        self.assertEqual(state.get_canonical_symptoms_from_interpreter(), set())

    def test_get_canonical_symptoms_lowercases_and_strips(self):
        state = SessionState("s")
        state.structured_symptoms = InterpreterOutput(
            chief_complaint_tr="baş",
            symptoms=[
                SymptomItem(name_tr="  Baş Ağrısı  "),
                SymptomItem(name_tr="BULANTI"),
                SymptomItem(name_tr=""),  # empty name — should be skipped
            ],
        )
        # NOTE: str.lower() does *not* apply Turkish locale rules; ASCII "I"
        # lowercases to "i", not "ı". The orchestrator has always used plain
        # `.lower()`, so the canonical form of "BULANTI" is "bulanti".
        self.assertEqual(
            state.get_canonical_symptoms_from_interpreter(),
            {"baş ağrısı", "bulanti"},
        )


class SessionStateContextTests(unittest.TestCase):
    """`to_context` is the payload the orchestrator hands to sub-agents.
    Conditional fields mean a shape regression here cascades into
    every downstream LLM prompt."""

    def test_minimal_context_has_conversation_and_question_count_only(self):
        state = SessionState("s")
        ctx = state.to_context()
        self.assertEqual(ctx["conversation_history"], [])
        self.assertEqual(ctx["question_count"], 0)
        self.assertNotIn("structured_symptoms", ctx)
        self.assertNotIn("profile", ctx)
        self.assertNotIn("specialty_scores", ctx)

    def test_context_includes_profile_when_set(self):
        state = SessionState("s", profile=UserProfile(age=30, sex="M"))
        ctx = state.to_context()
        self.assertEqual(ctx["profile"]["age"], 30)
        self.assertEqual(ctx["profile"]["sex"], "M")

    def test_context_includes_structured_symptoms_when_set(self):
        state = SessionState("s")
        state.structured_symptoms = InterpreterOutput(chief_complaint_tr="baş ağrısı")
        ctx = state.to_context()
        self.assertIn("structured_symptoms", ctx)
        self.assertEqual(
            ctx["structured_symptoms"]["chief_complaint_tr"], "baş ağrısı"
        )

    def test_context_includes_scoring_fields_when_populated(self):
        state = SessionState("s")
        state.specialty_scores = {"internal_gi": {"score": 3.0}}
        state.top_specialty = {"id": "internal_gi", "score": 3.0}
        state.disease_candidates = [{"disease_label": "Gastroenterit", "score_0_1": 0.7}]
        state.final_specialty_scores = {"internal_gi": {"final_score": 4.2}}
        ctx = state.to_context()
        self.assertEqual(ctx["specialty_scores"], {"internal_gi": {"score": 3.0}})
        self.assertEqual(ctx["top_specialty"]["id"], "internal_gi")
        self.assertEqual(len(ctx["disease_candidates"]), 1)
        self.assertIn("final_specialty_scores", ctx)


class SessionStateSnapshotTests(unittest.TestCase):
    def test_state_dict_roundtrip_contains_all_documented_keys(self):
        state = SessionState("s")
        state.known_symptoms.add("öksürük")
        state.asked_symptoms.add("ateş")
        state.denied_symptoms.add("bulantı")
        state.answers = {"ateş": "no"}
        state.turn_index = 2
        state.stop_reason = "HIGH_CONFIDENCE_SINGLE_DISEASE"
        state.confidence = 0.81

        snap = state.to_state_dict()
        # Key shape contract the /debug endpoint depends on.
        for key in (
            "session_id",
            "chat_history",
            "negatives_checked",
            "specialty_scores",
            "top_specialty",
            "questions_asked",
            "disease_candidates",
            "final_specialty_scores",
            "asked_symptoms",
            "known_symptoms",
            "denied_symptoms",
            "turn_index",
            "stop_reason",
            "confidence",
            "answers",
        ):
            self.assertIn(key, snap)
        # Sets are serialized as sorted lists for JSON friendliness.
        self.assertEqual(snap["asked_symptoms"], ["ateş"])
        self.assertEqual(snap["known_symptoms"], ["öksürük"])
        self.assertEqual(snap["denied_symptoms"], ["bulantı"])
        self.assertEqual(snap["turn_index"], 2)
        self.assertEqual(snap["stop_reason"], "HIGH_CONFIDENCE_SINGLE_DISEASE")
        self.assertAlmostEqual(snap["confidence"], 0.81)

    def test_state_dict_profile_serializes_to_dict_when_present(self):
        state = SessionState("s", profile=UserProfile(age=5, sex="F"))
        snap = state.to_state_dict()
        self.assertEqual(snap["profile"]["age"], 5)
        self.assertEqual(snap["profile"]["sex"], "F")

    def test_state_dict_profile_is_none_when_absent(self):
        snap = SessionState("s").to_state_dict()
        self.assertIsNone(snap["profile"])


# ─── Orchestrator registry ────────────────────────────────────────────


class OrchestratorSessionRegistryTests(unittest.TestCase):
    """The in-memory `_sessions` dict backs `handle_turn`'s state lookup.
    A regression that forgot to store or retrieve would spawn a fresh
    state for every turn — users would see question_count always 0."""

    def test_get_session_returns_none_for_unknown_id(self):
        orch = Orchestrator()
        self.assertIsNone(orch.get_session("does-not-exist"))

    def test_create_session_stores_and_returns_same_instance(self):
        orch = Orchestrator()
        state = orch.create_session("sess-A")
        self.assertIs(orch.get_session("sess-A"), state)
        self.assertEqual(state.session_id, "sess-A")

    def test_create_session_preserves_profile(self):
        orch = Orchestrator()
        profile = UserProfile(age=65, sex="M", chronic_conditions_tr=["hipertansiyon"])
        state = orch.create_session("s", profile=profile)
        self.assertIs(state.profile, profile)

    def test_create_session_overwrites_existing(self):
        # Current contract: no guard — a second call with the same ID
        # replaces the state. Document it via test so a change later
        # surfaces deliberately.
        orch = Orchestrator()
        s1 = orch.create_session("sess")
        s1.known_symptoms.add("ateş")
        s2 = orch.create_session("sess")
        self.assertIsNot(s1, s2)
        self.assertEqual(s2.known_symptoms, set())


# ─── Negative-symptom keyword detection ───────────────────────────────


class UpdateNegativesFromConversationTests(unittest.TestCase):
    """The orchestrator scans the user's free text for "X yok" patterns
    AND answers of "hayır/yok/olmadı" to red-flag-shaped AI questions.
    Both branches must update `negatives_checked` because stop-condition
    logic reads that dict to decide whether safety gates are cleared."""

    def setUp(self):
        self.orch = Orchestrator()

    def test_explicit_no_breathing_issue_marks_severe_breathing(self):
        state = SessionState("s")
        state.conversation_history = [
            {"role": "user", "content": "başım ağrıyor ama nefes darlığı yok"},
        ]
        self.orch._update_negatives_from_conversation(state)
        self.assertTrue(state.negatives_checked["severe_breathing"])
        self.assertFalse(state.negatives_checked["cardiac"])  # unrelated

    def test_stroke_keywords_trigger_stroke_like(self):
        state = SessionState("s")
        state.conversation_history = [
            {"role": "user", "content": "güçsüzlük yok, konuşma bozukluğu yok"},
        ]
        self.orch._update_negatives_from_conversation(state)
        self.assertTrue(state.negatives_checked["stroke_like"])

    def test_ai_question_with_hayir_answer_flips_negative(self):
        # AI asks about shortness of breath; user says "hayır" — should
        # count as a checked negative for severe_breathing.
        state = SessionState("s")
        state.conversation_history = [
            {"role": "ai", "content": "nefes darlığınız var mı?"},
            {"role": "user", "content": "hayır"},
        ]
        self.orch._update_negatives_from_conversation(state)
        self.assertTrue(state.negatives_checked["severe_breathing"])

    def test_ai_asks_about_stroke_symptom_and_user_says_yok(self):
        state = SessionState("s")
        state.conversation_history = [
            {"role": "ai", "content": "güçsüzlük hissettiniz mi?"},
            {"role": "user", "content": "yok"},
        ]
        self.orch._update_negatives_from_conversation(state)
        self.assertTrue(state.negatives_checked["stroke_like"])

    def test_empty_conversation_leaves_all_negatives_unchecked(self):
        state = SessionState("s")
        self.orch._update_negatives_from_conversation(state)
        self.assertFalse(any(state.negatives_checked.values()))

    def test_user_message_without_keywords_does_not_trip_anything(self):
        state = SessionState("s")
        state.conversation_history = [
            {"role": "user", "content": "başım ağrıyor"},
        ]
        self.orch._update_negatives_from_conversation(state)
        self.assertFalse(any(state.negatives_checked.values()))


# ─── Update known/denied symptoms from yes/no answer ──────────────────


class UpdateKnownSymptomsFromAnswerTests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_positive_answer_adds_to_known_symptoms(self):
        state = SessionState("s")
        state.asked_symptoms.add("ateş")
        state.conversation_history = [
            {"role": "ai", "content": "Ateşiniz var mı?"},
            {"role": "user", "content": "evet"},
        ]
        self.orch._update_known_symptoms_from_answer(state, "evet")
        self.assertIn("ateş", state.known_symptoms)
        self.assertNotIn("ateş", state.denied_symptoms)

    def test_negative_answer_adds_to_denied_symptoms(self):
        state = SessionState("s")
        state.asked_symptoms.add("ateş")
        state.conversation_history = [
            {"role": "ai", "content": "Ateşiniz var mı?"},
            {"role": "user", "content": "hayır"},
        ]
        self.orch._update_known_symptoms_from_answer(state, "hayır")
        self.assertIn("ateş", state.denied_symptoms)
        self.assertNotIn("ateş", state.known_symptoms)

    def test_ambiguous_answer_updates_nothing(self):
        state = SessionState("s")
        state.asked_symptoms.add("ateş")
        state.conversation_history = [
            {"role": "ai", "content": "Ateşiniz var mı?"},
            {"role": "user", "content": "belki"},
        ]
        self.orch._update_known_symptoms_from_answer(state, "belki")
        self.assertNotIn("ateş", state.known_symptoms)
        self.assertNotIn("ateş", state.denied_symptoms)

    def test_empty_history_is_a_noop(self):
        state = SessionState("s")
        state.asked_symptoms.add("ateş")
        self.orch._update_known_symptoms_from_answer(state, "evet")
        # No conversation → early return, nothing added.
        self.assertNotIn("ateş", state.known_symptoms)

    def test_no_asked_symptoms_is_a_noop(self):
        state = SessionState("s")
        state.conversation_history = [
            {"role": "ai", "content": "Ateşiniz var mı?"},
            {"role": "user", "content": "evet"},
        ]
        # Nothing in asked_symptoms → early return.
        self.orch._update_known_symptoms_from_answer(state, "evet")
        self.assertEqual(state.known_symptoms, set())


# ─── Confidence computation ───────────────────────────────────────────


class ComputeConfidenceTests(unittest.TestCase):
    """Confidence = clip(top1 * 0.75 + gap * 0.6, 0, 1) where gap = top1 - top2.
    Pinning the formula here means a drift in the weights shows up
    immediately instead of silently inflating or deflating UI badges."""

    def setUp(self):
        self.orch = Orchestrator()

    def test_zero_candidates_returns_zero(self):
        state = SessionState("s")
        self.assertEqual(self.orch._compute_confidence(state), 0.0)

    def test_single_high_candidate_scales_with_top1(self):
        state = SessionState("s")
        state.disease_candidates = [{"score_0_1": 0.8}]
        # top1=0.8, top2=0 → gap=0.8 → 0.8*0.75 + 0.8*0.6 = 0.6 + 0.48 = 1.08 → clipped to 1.0
        self.assertEqual(self.orch._compute_confidence(state), 1.0)

    def test_two_close_candidates_yield_low_confidence(self):
        state = SessionState("s")
        state.disease_candidates = [
            {"score_0_1": 0.4},
            {"score_0_1": 0.39},
        ]
        # 0.4*0.75 + 0.01*0.6 = 0.3 + 0.006 = 0.306 → rounded to 0.306
        self.assertAlmostEqual(
            self.orch._compute_confidence(state), 0.306, places=3
        )

    def test_confidence_is_clipped_below_one(self):
        state = SessionState("s")
        state.disease_candidates = [
            {"score_0_1": 1.0},
            {"score_0_1": 0.0},
        ]
        # 1.0*0.75 + 1.0*0.6 = 1.35 → clipped to 1.0
        self.assertEqual(self.orch._compute_confidence(state), 1.0)


# ─── Stop-condition v4 (deterministic branches) ───────────────────────


class ShouldStopV4Tests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_max_questions_reached_sets_low_confidence(self):
        state = SessionState("s")
        state.turn_index = 99
        self.assertTrue(self.orch._should_stop_v4(state))
        self.assertEqual(state.stop_reason, "MAX_QUESTIONS_REACHED")
        self.assertTrue(state.low_confidence)

    def test_high_confidence_single_disease_triggers_stop(self):
        state = SessionState("s")
        state.disease_candidates = [{"disease_label": "Gastroenterit", "score_0_1": 0.9}]
        self.assertTrue(self.orch._should_stop_v4(state))
        self.assertEqual(state.stop_reason, "HIGH_CONFIDENCE_SINGLE_DISEASE")
        self.assertFalse(state.low_confidence)

    def test_clear_specialty_winner_triggers_stop(self):
        state = SessionState("s")
        # Low top-disease score → skips that branch; big specialty gap → this branch.
        # NOTE: final_decision_engine.get_ranked_specialties sorts on
        # `keyword_score` as the secondary key, so the fixture must include it
        # alongside the primary `final_score` — otherwise we'd hit a KeyError
        # before ever exercising the stop-condition logic we're here to test.
        state.disease_candidates = [{"disease_label": "x", "score_0_1": 0.1}]
        state.final_specialty_scores = {
            "cardiology": {
                "final_score": 8.0, "rules_score": 5,
                "prior_score": 3, "keyword_score": 5,
            },
            "internal_gi": {
                "final_score": 1.0, "rules_score": 1,
                "prior_score": 0, "keyword_score": 1,
            },
        }
        self.assertTrue(self.orch._should_stop_v4(state))
        self.assertEqual(state.stop_reason, "CLEAR_SPECIALTY_WINNER")

    def test_low_signal_does_not_stop(self):
        state = SessionState("s")
        state.disease_candidates = [{"disease_label": "x", "score_0_1": 0.2}]
        state.final_specialty_scores = {
            "a": {
                "final_score": 1.0, "rules_score": 1,
                "prior_score": 0, "keyword_score": 1,
            },
            "b": {
                "final_score": 0.9, "rules_score": 1,
                "prior_score": 0, "keyword_score": 1,
            },
        }
        # Low score + thin gap → continue asking.
        self.assertFalse(self.orch._should_stop_v4(state))
        self.assertIsNone(state.stop_reason)


# ─── Doctor summary sentence ──────────────────────────────────────────


class BuildDoctorSummarySentenceTests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_empty_state_returns_empty_string(self):
        state = SessionState("s")
        self.assertEqual(self.orch._build_doctor_summary_sentence(state), "")

    def test_duration_sentence_for_known_symptom(self):
        state = SessionState("s")
        state.known_symptoms = {"öksürük"}
        state.parsed_answers = {"öksürük süresi": {"duration_days": 3}}
        sentence = self.orch._build_doctor_summary_sentence(state)
        self.assertIn("3 gündür öksürük var", sentence)

    def test_timing_and_severity_appended_to_duration_sentence(self):
        state = SessionState("s")
        state.known_symptoms = {"öksürük"}
        state.parsed_answers = {
            "öksürük süresi": {
                "duration_days": 5,
                "timing": "gece",
                "severity_0_10": 7,
            }
        }
        sentence = self.orch._build_doctor_summary_sentence(state)
        self.assertIn("5 gündür öksürük var", sentence)
        self.assertIn("gece", sentence)
        self.assertIn("şiddet 7/10", sentence)

    def test_plain_known_symptoms_appear_as_var_sentences(self):
        state = SessionState("s")
        state.known_symptoms = {"ateş", "baş ağrısı"}
        sentence = self.orch._build_doctor_summary_sentence(state)
        # Order-independent membership check.
        self.assertIn("Ateş var.", sentence)
        self.assertIn("Baş ağrısı var.", sentence)

    def test_denied_answers_appear_as_yok_sentences(self):
        state = SessionState("s")
        state.answers = {"bulantı": "hayır"}
        sentence = self.orch._build_doctor_summary_sentence(state)
        self.assertIn("Bulantı yok.", sentence)


# ─── Result payload (deterministic) ───────────────────────────────────


class BuildResultPayloadTests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_payload_has_expected_shape(self):
        state = SessionState("s")
        state.known_symptoms = {"baş ağrısı"}
        state.top_specialty = {"id": "neurology", "specialty_tr": "Nöroloji"}
        state.disease_candidates = [
            {"disease_label": "Migren", "score_0_1": 0.72},
            {"disease_label": "Gerilim tipi", "score_0_1": 0.31},
        ]
        payload = self.orch._build_result_payload(state)
        self.assertIn("urgency", payload)
        self.assertIn("recommended_specialty", payload)
        self.assertIn("top_conditions", payload)
        self.assertIn("doctor_ready_summary_tr", payload)
        self.assertIn("safety_notes_tr", payload)
        self.assertEqual(payload["recommended_specialty"]["id"], "neurology")
        self.assertEqual(payload["recommended_specialty"]["name_tr"], "Nöroloji")

    def test_urgency_escalates_to_same_day_for_heart_attack(self):
        state = SessionState("s")
        state.disease_candidates = [
            {"disease_label": "Heart attack (myocardial infarction)", "score_0_1": 0.65},
        ]
        payload = self.orch._build_result_payload(state)
        self.assertEqual(payload["urgency"], "SAME_DAY")

    def test_urgency_defaults_to_routine_for_benign_disease(self):
        state = SessionState("s")
        state.disease_candidates = [
            {"disease_label": "Common cold", "score_0_1": 0.5},
        ]
        payload = self.orch._build_result_payload(state)
        self.assertEqual(payload["urgency"], "ROUTINE")

    def test_neurology_top_specialty_appends_escalation_note(self):
        state = SessionState("s")
        state.top_specialty = {"id": "neurology", "specialty_tr": "Nöroloji"}
        payload = self.orch._build_result_payload(state)
        joined = " ".join(payload["safety_notes_tr"])
        self.assertIn("Ani bilinç kaybı", joined)

    def test_no_specialty_uses_safe_default(self):
        state = SessionState("s")
        payload = self.orch._build_result_payload(state)
        self.assertEqual(payload["recommended_specialty"]["id"], "internal_gi")
        self.assertEqual(payload["recommended_specialty"]["name_tr"], "Dahiliye")


# ─── Message formatters ───────────────────────────────────────────────


class FormatEmergencyMessageTests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_emergency_message_includes_header_and_reason(self):
        emerg = SafetyGuardOutput(
            status="EMERGENCY",
            reason="Göğüs ağrısı + nefes darlığı",
            emergency_instructions=["112'yi arayın", "Hareketsiz kalın"],
        )
        msg = self.orch._format_emergency_message(emerg)
        self.assertIn("ACİL DURUM UYARISI", msg)
        self.assertIn("Göğüs ağrısı + nefes darlığı", msg)
        self.assertIn("• 112'yi arayın", msg)
        self.assertIn("• Hareketsiz kalın", msg)

    def test_emergency_message_without_reason_still_has_header(self):
        emerg = SafetyGuardOutput(
            status="EMERGENCY", reason="", emergency_instructions=["112'yi arayın"]
        )
        msg = self.orch._format_emergency_message(emerg)
        self.assertIn("ACİL DURUM UYARISI", msg)
        self.assertIn("• 112'yi arayın", msg)


class FormatResultMessageTests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_result_message_lists_candidates_with_percentages(self):
        reasoning = ReasoningOutput(
            risk_level="LOW",
            candidates=[
                CandidateCondition(label_tr="Migren", probability_0_1=0.72),
                CandidateCondition(label_tr="Gerilim tipi", probability_0_1=0.25),
            ],
        )
        routing = RoutingOutput(
            recommended_specialty_tr="Nöroloji",
            urgency="ROUTINE",
        )
        msg = self.orch._format_result_message(reasoning, routing)
        self.assertIn("%72 - Migren", msg)
        self.assertIn("%25 - Gerilim tipi", msg)
        self.assertIn("Önerilen Branş: Nöroloji", msg)
        self.assertIn("Aciliyet: Rutin", msg)

    def test_urgency_map_translates_er_now_to_turkish(self):
        reasoning = ReasoningOutput(risk_level="HIGH", candidates=[])
        routing = RoutingOutput(recommended_specialty_tr="Kardiyoloji", urgency="ER_NOW")
        msg = self.orch._format_result_message(reasoning, routing)
        self.assertIn("Aciliyet: Hemen Acil", msg)

    def test_watchouts_section_appears_when_populated(self):
        reasoning = ReasoningOutput(risk_level="MEDIUM", candidates=[])
        routing = RoutingOutput(
            recommended_specialty_tr="Dahiliye",
            urgency="SAME_DAY",
            emergency_watchouts_tr=["Nefes darlığı artarsa acile gidin"],
        )
        msg = self.orch._format_result_message(reasoning, routing)
        self.assertIn("Şu belirtiler gelişirse acile gidin:", msg)
        self.assertIn("• Nefes darlığı artarsa acile gidin", msg)

    def test_no_watchouts_skips_section(self):
        reasoning = ReasoningOutput(risk_level="LOW", candidates=[])
        routing = RoutingOutput(
            recommended_specialty_tr="Dahiliye",
            urgency="ROUTINE",
            emergency_watchouts_tr=[],
        )
        msg = self.orch._format_result_message(reasoning, routing)
        self.assertNotIn("Şu belirtiler gelişirse", msg)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
