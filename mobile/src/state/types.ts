// ─── V4 Unified Triage Types ───

export type EnvelopeType = "QUESTION" | "RESULT" | "EMERGENCY" | "ERROR";

export type AnswerType = "yes_no" | "free_text" | "number" | "multi_choice";

export type TriageTurnRequest = {
  session_id: string | null;
  locale: "tr-TR";
  user_message: string;
  answer?: { canonical: string; value: string } | null;
  lat?: number | null;
  lon?: number | null;
};

export type QuestionPayload = {
  question_id: string;
  canonical: string;
  question_tr: string;
  answer_type: AnswerType;
  choices_tr?: string[] | null;
  why_asking_tr?: string | null;
};

export type RecommendedSpecialty = {
  id: string;
  name_tr: string;
};

export type TopCondition = {
  disease_label: string;
  score_0_1: number;
  // C2 "possible conditions" metadata. All optional — pre-C2 sessions
  // and Kaggle-derived candidates will be missing most of these.
  source_type?: "curated" | "kaggle_candidate";
  disease_description?: string;            // EN description (Kaggle)
  disease_description_tr?: string;         // TR description (curated)
  icd10?: string;
  doktora_sorulacak_sorular_tr?: string[];
  izlenecek_belirtiler_tr?: string[];
  ne_zaman_tekrar_basvur_tr?: string[];
  self_care_tr?: string[];
  aciliyet_notu_tr?: string;
  // Short one-liner attached to Kaggle-candidate entries via
  // kaggle_condition_meta.json (B3). Rendered under description.
  ipucu_tr?: string;
  disclaimer_tr?: string;
};

export type ResultPayload = {
  urgency: "EMERGENCY" | "SAME_DAY" | "ROUTINE";
  recommended_specialty: RecommendedSpecialty;
  top_conditions: TopCondition[];
  doctor_ready_summary_tr: string[];
  safety_notes_tr: string[];
  // v5: backend-authoritative confidence + explanation
  confidence_0_1?: number;
  confidence_label_tr?: string;
  confidence_explain_tr?: string;
  why_specialty_tr?: string[];
  stop_reason?: string;
};

export type EmergencyPayload = {
  urgency: "EMERGENCY";
  reason_tr: string;
  instructions_tr: string[];
};

export type ErrorPayload = {
  code: string;
  message_tr: string;
  retryable?: boolean;
};

export type Envelope =
  | { type: "QUESTION"; session_id: string; turn_index: number; payload: QuestionPayload }
  | { type: "RESULT"; session_id: string; turn_index: number; payload: ResultPayload }
  | { type: "EMERGENCY"; session_id: string; turn_index: number; payload: EmergencyPayload }
  | { type: "ERROR"; session_id: string; turn_index: number; payload: ErrorPayload };

export type Msg = {
  role: "user" | "assistant";
  text: string;
};
