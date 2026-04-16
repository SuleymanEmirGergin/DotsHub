/**
 * Merkezi admin TypeScript interface'leri.
 * Tüm admin sayfaları bu dosyadan import eder — sayfalar arası `any` kullanımını önler.
 */

// ─── Health / Badge ───────────────────────────────────────────────

export type HealthStatus = "INFO" | "OK" | "WARN" | "CRIT";

// ─── Session ─────────────────────────────────────────────────────

export interface SessionMeta {
  risk_level?: string;
  risk?: { level: string; score_0_1: number };
  risk_score_0_1?: number;
  duration_days?: number;
  same_day?: boolean;
  [key: string]: unknown;
}

export interface SessionRow {
  id: string;
  session_id: string;
  created_at: string;
  updated_at: string;
  envelope_type: string | null;
  stop_reason: string | null;
  confidence_0_1: number | null;
  confidence_label_tr: string | null;
  recommended_specialty_tr: string | null;
  recommended_specialty_id: number | null;
  extracted_canonicals: string[];
  meta: SessionMeta;
  device_id?: string | null;
}

export interface SessionDetail {
  session: SessionRow;
  events: SessionEvent[];
  feedback: FeedbackRow[];
}

export interface SessionEvent {
  id: string;
  created_at: string;
  event_type: string;
  payload: Record<string, unknown>;
}

// ─── Feedback ────────────────────────────────────────────────────

export interface FeedbackRow {
  id: string;
  session_id: string;
  rating: "up" | "down";
  comment: string | null;
  user_selected_specialty_id: string | null;
  user_selected_specialty_tr: string | null;
  created_at: string;
}

// ─── Tuning Task ─────────────────────────────────────────────────

export interface TuningTaskRow {
  id: string;
  task_type: string;
  status: string;
  session_id: string;
  payload: Record<string, unknown>;
  patch: Record<string, unknown> | null;
  created_at: string;
  applied_at: string | null;
  created_by: string | null;
}

// ─── Deployment ──────────────────────────────────────────────────

export interface DeploymentRow {
  id: string;
  version: string;
  deployed_at: string | null;
  last_deployment_at: string | null;
  notes: string | null;
}

export type ImpactPeriod = {
  total?: number;
  down_rate?: number;
  avg_confidence?: number;
  avg_questions?: number;
  low_conf_rate?: number;
  high_risk_rate?: number;
  daily_series?: Array<{ down_rate?: number; confidence?: number }>;
};

export interface DeploymentImpact {
  before?: ImpactPeriod;
  after?: ImpactPeriod;
  delta?: { down_rate?: number; avg_confidence?: number; avg_questions?: number };
  daily?: Array<{ down_rate?: number; confidence?: number }>;
}

export interface GuardrailsConfig {
  thresholds: Record<string, number>;
  min_feedback_after: number;
}

// ─── Tuning Report ───────────────────────────────────────────────

export interface ReportFile {
  name: string;
  size?: number;
  created_at?: string;
}

export interface SynonymSuggestion {
  token: string;
  suggested_canonical: string;
  support_count: number;
}

export interface TuningReport {
  synonym_suggestions?: SynonymSuggestion[];
  [key: string]: unknown;
}

// ─── Admin User ──────────────────────────────────────────────────

export interface AdminUser {
  id: string;
  email: string;
  created_at: string;
  role?: string;
}

// ─── Stats / Overview ────────────────────────────────────────────

export interface StatsOverview {
  total: number;
  by_envelope_type: Record<string, number>;
  by_stop_reason: Record<string, number>;
  by_risk_level?: Record<string, number>;
  low_confidence_count: number;
  low_confidence_rate: number;
  health?: {
    overall: HealthStatus;
    samples: number;
    low_conf_rate: number;
    high_risk_rate: number;
    low_conf_status: HealthStatus;
    high_risk_status: HealthStatus;
    thresholds: Record<string, number>;
  };
}

export interface SeriesPoint {
  low_conf_rate?: number;
  high_risk_rate?: number;
  bucket?: string;
}
