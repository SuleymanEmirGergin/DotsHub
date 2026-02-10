/**
 * API client V2 — aligned with openapi.yaml
 *
 * Endpoints:
 *   POST /v1/session/start         { user_input_tr, profile }
 *   POST /v1/session/{id}/message  { user_input_tr }
 *   GET  /v1/session/{id}/state
 *   GET  /v1/session/{id}/result
 *   GET  /v1/session/{id}/summary
 */

import { API_BASE } from "@/src/config/runtime";

const API_BASE_URL = `${API_BASE}/v1`;

// ─── Types ───

export interface Profile {
  age?: number;
  sex?: string;
  pregnancy?: string | null;
  chronic_conditions_tr?: string[];
  medications_tr?: string[];
  allergies_tr?: string[];
}

// Backward compat alias
export type UserProfile = Profile;

export interface Meta {
  disclaimer_tr: string;
  timestamp: string;
  model_info?: Record<string, any>;
  debug?: Record<string, any>;
  facility_discovery?: FacilityDiscovery;
}

export interface FacilityDiscoveryItem {
  name: string;
  type: string;
  address: string;
  distance_km?: number;
}

export interface FacilityDiscovery {
  specialty_id: string;
  city: string;
  items: FacilityDiscoveryItem[];
  disclaimer: string;
}

export interface UiHints {
  quick_replies?: boolean;
  [key: string]: any;
}

export interface QuestionPayload {
  question_tr: string;
  answer_type: 'yes_no' | 'number' | 'multiple_choice' | 'free_text';
  choices_tr: string[];
  ui_hints?: UiHints;
}

export interface CandidateCondition {
  label_tr: string;
  probability_0_1: number;
  supporting_evidence_tr?: string[];
  contradicting_evidence_tr?: string[];
}

export interface DoctorReadySummary {
  symptoms_tr: string[];
  timeline_tr: string;
  qa_highlights_tr: string[];
  risk_level: string;
}

export interface ResultPayload {
  recommended_specialty_tr: string;
  urgency: 'ER_NOW' | 'SAME_DAY' | 'WITHIN_3_DAYS' | 'ROUTINE';
  candidates_tr: CandidateCondition[];
  rationale_tr: string[];
  emergency_watchouts_tr: string[];
  doctor_ready_summary_tr: DoctorReadySummary;
  specialty_scores?: Record<string, any>;
}

export interface EmergencyPayload {
  reason_tr: string;
  instructions_tr: string[];
  missing_info_to_confirm_tr: string[];
}

export interface ErrorPayload {
  code: string;
  message_tr: string;
  retryable: boolean;
}

export type EnvelopeType = 'QUESTION' | 'RESULT' | 'EMERGENCY' | 'ERROR';

export interface Envelope {
  type: EnvelopeType;
  session_id: string;
  payload: QuestionPayload | ResultPayload | EmergencyPayload | ErrorPayload;
  meta: Meta;
}

export interface SummaryResponse {
  session_id: string;
  doctor_ready_summary_tr: DoctorReadySummary;
  candidates: CandidateCondition[];
  routing: {
    recommended_specialty_tr: string;
    urgency: string;
    rationale_tr: string[];
    emergency_watchouts_tr: string[];
    doctor_ready_summary_tr: DoctorReadySummary;
  };
  messages: Array<{ role: string; content: string; timestamp: string }>;
  disclaimer: string;
}

export interface ChatMessage {
  role: 'user' | 'ai' | 'system';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

// ─── Client ───

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  /**
   * POST /v1/session/start
   */
  async startSession(userInputTr: string, profile?: Profile): Promise<Envelope> {
    return this.request<Envelope>('/session/start', {
      method: 'POST',
      body: JSON.stringify({ user_input_tr: userInputTr, profile }),
    });
  }

  /**
   * POST /v1/session/{session_id}/message
   */
  async sendMessage(sessionId: string, userInputTr: string): Promise<Envelope> {
    return this.request<Envelope>(`/session/${sessionId}/message`, {
      method: 'POST',
      body: JSON.stringify({ user_input_tr: userInputTr }),
    });
  }

  /**
   * GET /v1/session/{session_id}/result
   */
  async getResult(sessionId: string): Promise<Envelope> {
    return this.request<Envelope>(`/session/${sessionId}/result`);
  }

  /**
   * GET /v1/session/{session_id}/summary
   */
  async getSummary(sessionId: string): Promise<SummaryResponse> {
    return this.request<SummaryResponse>(`/session/${sessionId}/summary`);
  }

  /**
   * GET /v1/session/{session_id}/state (debug)
   */
  async getState(sessionId: string): Promise<any> {
    return this.request<any>(`/session/${sessionId}/state`);
  }
}

export const api = new ApiClient();
