"""Pydantic schemas for API request/response validation (V3 — unified triage turn)."""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Any
from datetime import datetime


# ─── Profile ───

class Profile(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = None
    pregnancy: Optional[str] = None
    chronic_conditions_tr: List[str] = Field(default_factory=list)
    medications_tr: List[str] = Field(default_factory=list)
    allergies_tr: List[str] = Field(default_factory=list)


# ─── Request Schemas ───

# V3 unified turn request
class TriageAnswer(BaseModel):
    canonical: str = Field(..., description="Canonical symptom name the question was about")
    value: str = Field(..., description="User's answer (yes/no/free text)")


class TriageTurnRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="null means start new session")
    locale: str = Field("tr-TR")
    user_message: str = Field("", description="Free text symptoms (empty allowed when answering)")
    answer: Optional[TriageAnswer] = Field(None, description="User answer to the last question")
    lat: Optional[float] = Field(None, description="User latitude for facility discovery (optional)")
    lon: Optional[float] = Field(None, description="User longitude for facility discovery (optional)")
    device_id: Optional[str] = Field(
        None,
        description=(
            "Stable per-install device identifier. Links the session to a "
            "push_tokens row so the backend can send follow-up reminders. "
            "Optional — old clients don't send it."
        ),
        max_length=128,
    )


# Legacy request schemas (kept for backward compat)
class SessionStartRequest(BaseModel):
    user_input_tr: str = Field(..., min_length=3, description="Free-text symptom description (Turkish)")
    profile: Optional[Profile] = None


class MessageRequest(BaseModel):
    user_input_tr: str = Field(..., min_length=1, description="User answer or follow-up (Turkish)")


# ─── Backward-compat alias ───
UserProfile = Profile


# ─── Agent Output Schemas (V2: _tr fields) ───

class SymptomItem(BaseModel):
    name_tr: str = ""
    onset_tr: Optional[str] = None
    duration_tr: Optional[str] = None
    severity_0_10: Optional[float] = None
    notes_tr: Optional[str] = None


class SymptomContext(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = None
    pregnancy: Optional[str] = None
    chronic_conditions_tr: List[str] = Field(default_factory=list)
    medications_tr: List[str] = Field(default_factory=list)
    allergies_tr: List[str] = Field(default_factory=list)


class InterpreterOutput(BaseModel):
    chief_complaint_tr: str = ""
    symptoms: List[SymptomItem] = Field(default_factory=list)
    negatives_tr: List[str] = Field(default_factory=list)
    context: SymptomContext = Field(default_factory=SymptomContext)


class SafetyGuardOutput(BaseModel):
    status: Literal["EMERGENCY", "OK"]
    reason: str = ""
    emergency_instructions: List[str] = Field(default_factory=list)
    missing_info_to_confirm: List[str] = Field(default_factory=list)


class QuestionOutput(BaseModel):
    question_tr: str = ""
    answer_type: Literal["yes_no", "number", "multiple_choice", "free_text"] = "free_text"
    choices_tr: List[str] = Field(default_factory=list)
    why_this_question_tr: str = ""
    stop: bool = False


class CandidateCondition(BaseModel):
    label_tr: str = ""
    probability_0_1: float = 0.0
    supporting_evidence_tr: List[str] = Field(default_factory=list)
    contradicting_evidence_tr: List[str] = Field(default_factory=list)


class ReasoningOutput(BaseModel):
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    candidates: List[CandidateCondition] = Field(default_factory=list)
    confidence_notes_tr: str = ""
    need_more_info_tr: List[str] = Field(default_factory=list)


class DoctorReadySummary(BaseModel):
    symptoms_tr: List[str] = Field(default_factory=list)
    timeline_tr: str = ""
    qa_highlights_tr: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"


class RoutingOutput(BaseModel):
    recommended_specialty_tr: str = ""
    urgency: Literal["ER_NOW", "SAME_DAY", "WITHIN_3_DAYS", "ROUTINE"] = "ROUTINE"
    rationale_tr: List[str] = Field(default_factory=list)
    emergency_watchouts_tr: List[str] = Field(default_factory=list)
    doctor_ready_summary_tr: DoctorReadySummary = Field(default_factory=DoctorReadySummary)


# ─── Envelope Response (V3 — unified triage turn) ───

class FacilityDiscoveryItem(BaseModel):
    name: str
    type: str
    address: str
    distance_km: Optional[float] = None


class FacilityDiscoveryMeta(BaseModel):
    specialty_id: str
    city: str
    items: List[FacilityDiscoveryItem] = Field(default_factory=list)
    disclaimer: str


class Meta(BaseModel):
    disclaimer_tr: str = "Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır."
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_info: Optional[dict] = None
    debug: Optional[dict] = None
    facility_discovery: Optional[FacilityDiscoveryMeta] = None


class UiHints(BaseModel):
    quick_replies: Optional[bool] = None


# V3 question payload (includes question_id + canonical for answer tracking)
class QuestionPayload(BaseModel):
    question_id: str = ""
    canonical: str = ""
    question_tr: str
    answer_type: str = "free_text"
    choices_tr: List[str] = Field(default_factory=list)
    why_asking_tr: Optional[str] = None
    ui_hints: Optional[UiHints] = None


# V3 recommended specialty sub-object
class RecommendedSpecialty(BaseModel):
    id: str
    name_tr: str


# V3 disease condition entry.
#
# Schema covers both Kaggle candidates and curated injections:
#   source_type="curated"         → carries the full patient-prep
#                                    metadata (description, 4 prep
#                                    arrays, aciliyet_notu, icd10).
#   source_type="kaggle_candidate" → carries the lighter B3 meta
#                                    (icd10 + disease_description_tr
#                                    + ipucu_tr) when the label has
#                                    an entry in kaggle_condition_meta.
# All metadata fields are Optional because pre-C2 sessions and
# labels without curated/kaggle meta will omit them.
class TopConditionEntry(BaseModel):
    disease_label: str
    score_0_1: float
    # Kaggle-origin English description (fallback when no TR is attached).
    disease_description: Optional[str] = None
    # C2 — source tagging so the UI can badge / gate differently.
    source_type: Optional[str] = None
    # Curated + Kaggle both: ICD-10 code (when catalog has one).
    icd10: Optional[str] = None
    # Curated + Kaggle both: short TR description paragraph.
    disease_description_tr: Optional[str] = None
    # Curated only: patient prep blocks.
    doktora_sorulacak_sorular_tr: Optional[List[str]] = None
    izlenecek_belirtiler_tr: Optional[List[str]] = None
    ne_zaman_tekrar_basvur_tr: Optional[List[str]] = None
    self_care_tr: Optional[List[str]] = None
    aciliyet_notu_tr: Optional[str] = None
    # B3 only: single-sentence prep hint attached to Kaggle candidates.
    ipucu_tr: Optional[str] = None
    # Always attached at render time so UI can footer-disclaim per row.
    disclaimer_tr: Optional[str] = None

    # Preserve internal debug fields (like the A1 _source_label added
    # by apply_label_overrides) without rejecting them at validation.
    model_config = {"extra": "allow"}


# V3 result payload (clinical quality)
class ResultPayload(BaseModel):
    urgency: str = "ROUTINE"
    recommended_specialty: RecommendedSpecialty = Field(default_factory=lambda: RecommendedSpecialty(id="unknown", name_tr="Bilinmiyor"))
    top_conditions: List[TopConditionEntry] = Field(default_factory=list)
    doctor_ready_summary_tr: List[str] = Field(default_factory=list)
    safety_notes_tr: List[str] = Field(default_factory=list)
    # Legacy fields kept for backward compat
    recommended_specialty_tr: str = ""
    candidates_tr: List[CandidateCondition] = Field(default_factory=list)
    rationale_tr: List[str] = Field(default_factory=list)
    emergency_watchouts_tr: List[str] = Field(default_factory=list)
    specialty_scores: Optional[dict] = None


class EmergencyPayload(BaseModel):
    urgency: str = "EMERGENCY"
    reason_tr: str = ""
    instructions_tr: List[str] = Field(default_factory=list)
    missing_info_to_confirm_tr: List[str] = Field(default_factory=list)


class ErrorPayload(BaseModel):
    code: str = "UNKNOWN"
    message_tr: str = ""
    retryable: bool = True


class Envelope(BaseModel):
    # Health-tourism pivot extends the envelope union: QUOTE returns a
    # ranked clinic+package list for a specific procedure; ITINERARY
    # returns a day-by-day plan once a clinic is selected. Existing
    # triage envelope types stay unchanged so the contract is purely
    # additive — old clients keep working.
    type: Literal[
        "QUESTION", "RESULT", "EMERGENCY", "ERROR", "QUOTE", "ITINERARY"
    ]
    session_id: str
    turn_index: int = 0
    payload: Any
    meta: Meta = Field(default_factory=Meta)


# ──────────────────────────────────────────────────────────
# Health-tourism request/response schemas (v0)
# ──────────────────────────────────────────────────────────
#
# These types describe the contract for `POST /v1/quote`. The payload
# inside Envelope.payload uses dict[str, Any] (kept loose to mirror the
# existing triage payloads), but request/profile shapes are typed
# rigorously so the route handler validates input at the FastAPI layer.


class HealthTourismProfile(BaseModel):
    """Patient profile used by the fit-to-travel rule engine.

    Every flag is optional and defaults to False/unknown. The engine
    treats missing fields as "no concern signaled" — clinical truth is
    deferred to the in-person consultation. This profile is a screening
    layer, not a clearance.

    Add new flags to `KNOWN_TRIGGER_KEYS` in
    `backend/app/services/fit_to_travel.py` when extending.
    """

    age: Optional[int] = Field(default=None, ge=0, le=120)
    sex: Optional[Literal["male", "female", "other"]] = None
    bmi: Optional[float] = Field(default=None, ge=10.0, le=80.0)

    # Boolean trigger flags — match `trigger_keys` in fit_to_travel_rules.json.
    recent_mi: bool = False
    unstable_angina: bool = False
    decompensated_heart_failure: bool = False
    uncontrolled_hypertension: bool = False
    uncontrolled_diabetes: bool = False
    active_cancer: bool = False
    active_chemo: bool = False
    pregnancy: bool = False
    breastfeeding: bool = False
    smoker_active: bool = False
    dvt_history: bool = False
    anticoagulant_therapy: bool = False
    bisphosphonate_therapy: bool = False
    active_infection: bool = False
    active_eye_infection: bool = False
    dry_eye_severe: bool = False
    bruxism_severe: bool = False
    uncontrolled_thyroid: bool = False
    severe_copd: bool = False
    dialysis_dependent: bool = False
    bmi_over_35: bool = False
    bmi_over_55: bool = False


class QuoteRequest(BaseModel):
    """Body for `POST /v1/quote`.

    Either ``procedure_id`` (resolved by the client / earlier turn) or
    ``user_message`` (free-text, resolved server-side via the
    procedure_intent extractor) must be present.
    """

    procedure_id: Optional[str] = None
    user_message: Optional[str] = None
    profile: HealthTourismProfile = Field(default_factory=HealthTourismProfile)
    locale: str = "tr-TR"
    target_city: Optional[str] = None
    travel_origin_country: Optional[str] = None
    top_n: int = Field(default=5, ge=1, le=20)


class ClinicQuoteItem(BaseModel):
    """One ranked clinic in a QUOTE envelope payload."""

    clinic_id: str
    clinic_name: str
    city: str
    score_0_1: float
    price_eur: int
    price_band_eur: dict[str, int]
    package_features: List[str]
    languages: List[str]
    certifications: List[str]
    consult_response_hours: int
    average_rating_5: float
    map_url: Optional[str] = None
    why_recommended_tr: List[str] = Field(default_factory=list)


class FitToTravelWarning(BaseModel):
    """One fit-to-travel concern surfaced on a QUOTE envelope.

    Severity ``warn`` lets the quote proceed with the warning visible;
    severity ``block`` causes the route handler to return an
    EMERGENCY-style envelope instead of QUOTE — the caller must seek
    local care first.
    """

    rule_id: str
    severity: Literal["warn", "block"]
    reason_tr: str
    recommendation_tr: str


class ItineraryRequest(BaseModel):
    """Body for `POST /v1/quote/itinerary`.

    The patient has chosen a clinic from a prior QUOTE envelope and
    confirmed an arrival date; this request resolves to a day-by-day
    plan they can take to a doctor or travel agent. We re-run the
    fit-to-travel rules against the profile because a few weeks may
    have passed between the quote and the itinerary request — health
    state changes, the rules don't.
    """

    procedure_id: str
    clinic_id: str
    arrival_date: str  # ISO date "YYYY-MM-DD"
    profile: HealthTourismProfile = Field(default_factory=HealthTourismProfile)
    locale: str = "tr-TR"


# ─── Legacy compat / internal helpers ───

class ChatMessage(BaseModel):
    role: Literal["user", "ai", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[dict] = None


class SummaryResponse(BaseModel):
    session_id: str
    doctor_ready_summary_tr: DoctorReadySummary
    candidates: List[CandidateCondition]
    routing: RoutingOutput
    messages: List[ChatMessage]
    disclaimer: str = "Bu uygulama tanı koymaz. Bilgilendirme ve yönlendirme amaçlıdır."
