// ─── Health-tourism types (Session 17 pivot, mobile mirror) ───
//
// Mirrors the Pydantic shapes in
//   backend/app/models/schemas.py  (HealthTourismProfile, QuoteRequest,
//                                   ItineraryRequest, LeadRequest, etc.)
// and the QUOTE / ITINERARY envelope payloads emitted by
//   backend/app/api/routes/health_tourism/{quote,itinerary,lead}.py
//
// Kept in a separate file from the triage types so the HT flow is
// self-contained — easier to delete or replace if the pivot changes
// shape, and the bigger triage-side state stays readable.

export type Locale = "tr-TR" | "en-US" | "de-DE" | "ru-RU" | "ar-SA";

// ─── Profile (fit-to-travel screening inputs) ──────────────────────

// All flags optional / default false on the backend; we model them
// as a partial type so screens only have to set what's checked.
export type HealthTourismProfile = {
  age?: number | null;
  sex?: "male" | "female" | "other" | null;
  bmi?: number | null;

  recent_mi?: boolean;
  unstable_angina?: boolean;
  decompensated_heart_failure?: boolean;
  uncontrolled_hypertension?: boolean;
  uncontrolled_diabetes?: boolean;
  active_cancer?: boolean;
  active_chemo?: boolean;
  pregnancy?: boolean;
  breastfeeding?: boolean;
  smoker_active?: boolean;
  dvt_history?: boolean;
  anticoagulant_therapy?: boolean;
  bisphosphonate_therapy?: boolean;
  active_infection?: boolean;
  active_eye_infection?: boolean;
  dry_eye_severe?: boolean;
  bruxism_severe?: boolean;
  uncontrolled_thyroid?: boolean;
  severe_copd?: boolean;
  dialysis_dependent?: boolean;
  bmi_over_35?: boolean;
  bmi_over_55?: boolean;
};

// ─── Request bodies ────────────────────────────────────────────────

export type QuoteRequest = {
  /** Pre-resolved id from the procedure browse step (preferred). */
  procedure_id?: string;
  /** Free-text fallback; backend resolves via procedure_intent. */
  user_message?: string;
  profile?: HealthTourismProfile;
  locale?: Locale;
  target_city?: string;
  travel_origin_country?: string;
  /** Number of clinics to rank (default 5, max 20). */
  top_n?: number;
};

export type ItineraryRequest = {
  procedure_id: string;
  clinic_id: string;
  /** ISO date "YYYY-MM-DD". */
  arrival_date: string;
  profile?: HealthTourismProfile;
  locale?: Locale;
};

export type LeadContact = {
  name?: string;
  email?: string;
  phone?: string;
  preferred_contact?: "email" | "phone" | "whatsapp" | "any";
  best_time?: string;
};

export type LeadRequest = {
  procedure_id: string;
  clinic_id: string;
  contact: LeadContact;
  /** KVKK/GDPR gate — without it the operator gets a redacted webhook. */
  consent_to_share: boolean;
  locale?: Locale;
  notes?: string;
  /** payload.quote_id from the previous QUOTE envelope (audit trail). */
  quote_id?: string;
};

// ─── Envelope payload shapes ───────────────────────────────────────

export type ClinicQuoteItem = {
  clinic_id: string;
  clinic_name: string;
  city: string;
  score_0_1: number;
  price_eur: number;
  price_band_eur: { low?: number; mid?: number; high?: number };
  package_features: string[];
  languages: string[];
  certifications: string[];
  consult_response_hours: number;
  average_rating_5: number;
  map_url?: string | null;
  why_recommended_tr: string[];
};

export type FitToTravelWarning = {
  rule_id: string;
  severity: "warn" | "block";
  reason_tr: string;
  recommendation_tr: string;
};

export type QuotePayload = {
  quote_id: string;
  procedure: {
    id: string;
    name_tr: string;
    category?: string;
    duration_days?: { min_stay?: number; max_stay?: number; recovery_total?: number };
    post_op_no_fly_days?: number;
    anesthesia?: string;
    complexity?: string;
  };
  clinics: ClinicQuoteItem[];
  fit_to_travel_warnings: FitToTravelWarning[];
  intent_resolution?: Record<string, unknown> | null;
  currency: string; // "EUR"
  /** Optional LLM-generated narrative; null on cache miss. */
  summary_tr?: string | null;
};

export type ItineraryItem = {
  day: number;
  date: string;          // ISO "YYYY-MM-DD"
  category: string;      // "consultation" | "procedure" | "rest" | ...
  title_tr: string;
  description_tr: string;
  start_hour?: number;
  end_hour?: number;
};

export type ItineraryPayload = {
  procedure_id: string;
  procedure_name_tr: string;
  clinic_id: string;
  clinic_name: string;
  clinic_city: string;
  arrival_date: string;
  departure_date: string;
  total_days: number;
  items: ItineraryItem[];
  pre_op_requirements: string[];
  post_op_no_fly_days: number;
  post_op_followup_window_days: number;
  fit_to_travel_warnings: FitToTravelWarning[];
};

export type LeadAcceptedPayload = {
  code: "LEAD_ACCEPTED";
  lead_id: string;
  quote_id?: string | null;
  consent_to_share: boolean;
  webhook_status: "scheduled" | "not_configured";
  webhook_configured: boolean;
  persisted: boolean;
  next_steps_tr: string;
  procedure_id: string;
  procedure_name_tr: string;
  clinic_id: string;
  clinic_name: string;
  quoted_price_eur?: number | null;
};

// EMERGENCY envelope when fit-to-travel rule blocks travel.
export type FitToTravelBlockPayload = {
  urgency: "ROUTINE_BUT_NOT_TRAVEL_FIT";
  reason_tr: string;
  instructions_tr: string[];
  fit_to_travel_warnings: FitToTravelWarning[];
  procedure_id: string;
  procedure_name_tr: string;
};

export type HtErrorPayload = {
  code:
    | "PROCEDURE_UNRESOLVED"
    | "PROCEDURE_UNKNOWN"
    | "NO_PARTNER_CLINIC"
    | "CLINIC_PROCEDURE_MISMATCH"
    | "ARRIVAL_DATE_INVALID"
    | "ITINERARY_GENERATION_FAILED"
    | string;
  message_tr: string;
  retryable?: boolean;
  procedure_id?: string;
  clinic_id?: string;
};

export type HtEnvelope =
  | { type: "QUOTE"; session_id: string; turn_index: number; payload: QuotePayload }
  | { type: "ITINERARY"; session_id: string; turn_index: number; payload: ItineraryPayload }
  | { type: "RESULT"; session_id: string; turn_index: number; payload: LeadAcceptedPayload }
  | { type: "EMERGENCY"; session_id: string; turn_index: number; payload: FitToTravelBlockPayload }
  | { type: "ERROR"; session_id: string; turn_index: number; payload: HtErrorPayload };
