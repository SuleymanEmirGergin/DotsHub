/**
 * Sessions API client — wraps GET /v1/triage/sessions/{id}.
 *
 * Powers the History → Detail drill-down on mobile. The list endpoint
 * (/v1/triage/history) returns a thin summary; this one returns the
 * full row (specialty + confidence + top conditions + why-specialty +
 * emergency reason + the original symptom text) so the detail screen
 * can rebuild the result UI for a past session.
 *
 * Auth is by-possession-of-device-id (header). Wrong device id 404s
 * — that's deliberate (anti-IDOR; see backend route docstring).
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";
import {
  addApiBreadcrumb,
  addBreadcrumb,
} from "@/src/observability/breadcrumb";
import { getDeviceId } from "../../utils/deviceId";

export type SessionEnvelopeType = "QUESTION" | "RESULT" | "EMERGENCY" | "ERROR";

export interface SessionDetailTopCondition {
  disease_label?: string;
  score_0_1?: number;
  // Keep extra fields permissive — backend includes curated metadata
  // (icd10, disease_description_tr, …) when the capability flag is on.
  [key: string]: unknown;
}

export interface SessionDetail {
  id: string;
  session_id?: string | null;
  created_at: string;
  updated_at?: string | null;
  envelope_type: SessionEnvelopeType;
  turn_index: number;
  stop_reason?: string | null;
  locale?: string | null;

  recommended_specialty_id?: string | null;
  recommended_specialty_tr?: string | null;

  confidence_0_1?: number | null;
  confidence_label_tr?: string | null;
  confidence_explain_tr?: string | null;

  top_conditions: SessionDetailTopCondition[];
  why_specialty_tr: string[];

  emergency_rule_id?: string | null;
  emergency_reason_tr?: string | null;

  input_text?: string | null;
  asked_canonicals: string[];
  extracted_canonicals: string[];
  user_canonicals_tr: string[];
}

export class SessionDetailError extends Error {
  status: number;
  code?: string;
  message_tr?: string;

  constructor(message: string, status: number, code?: string, message_tr?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.message_tr = message_tr;
  }
}

/**
 * Fetch the full detail for one past triage session.
 *
 * Throws `SessionDetailError` with the HTTP status + the backend's
 * `{code, message_tr}` payload (when present) so callers can branch
 * on `code === "not_found"` vs `"session_detail_unavailable"` without
 * parsing strings.
 */
export async function getSessionDetail(
  sessionId: string,
): Promise<SessionDetail> {
  const deviceId = getDeviceId();

  addBreadcrumb(
    "sessions",
    `detail fetch begin id=${sessionId}`,
    { sessionId },
    "info",
  );

  const startedAt = Date.now();
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/triage/sessions/${encodeURIComponent(sessionId)}`,
      {
        method: "GET",
        headers: {
          "x-device-id": deviceId,
        },
      },
      12000,
    );

    addApiBreadcrumb({
      endpoint: "/v1/triage/sessions/{id}",
      method: "GET",
      status: res.status,
      durationMs: Date.now() - startedAt,
      level: res.ok ? "info" : "error",
    });

    if (!res.ok) {
      let detail: { code?: string; message_tr?: string } | null = null;
      try {
        const body = await res.json();
        if (body && typeof body === "object" && body.detail) {
          detail = body.detail;
        }
      } catch {
        // Non-JSON error body — fall back to status code only.
      }
      throw new SessionDetailError(
        detail?.message_tr || `HTTP ${res.status}`,
        res.status,
        detail?.code,
        detail?.message_tr,
      );
    }

    return (await res.json()) as SessionDetail;
  } catch (err) {
    if (err instanceof SessionDetailError) throw err;
    addApiBreadcrumb({
      endpoint: "/v1/triage/sessions/{id}",
      method: "GET",
      status: 0,
      durationMs: Date.now() - startedAt,
      level: "error",
      note: err instanceof Error ? err.name : "network",
    });
    throw err;
  }
}
