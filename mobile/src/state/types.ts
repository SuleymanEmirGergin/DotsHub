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
