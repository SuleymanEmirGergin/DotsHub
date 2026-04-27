/**
 * Consent API client — KVKK Md.6(2) / GDPR Art.9(2)(a) explicit consent.
 *
 * The intro screen calls `recordConsent` twice (terms_general +
 * health_data_processing) before letting the user proceed. Each call
 * is an INSERT-only audit row on the backend; see
 * `backend/sql/20260427_consent_records.sql` and
 * `backend/app/api/routes/consent.py`.
 *
 * Why we block the start button on this rather than fire-and-forget:
 * we promised the user (in the privacy notice) that the consent is
 * recorded. Silently dropping it on a network failure would create a
 * compliance gap — we'd hold session data without a stored consent
 * row to point at. Cost is one extra round trip on first launch;
 * subsequent launches don't re-prompt unless `consent_version` was
 * bumped.
 *
 * Breadcrumbs follow the same pattern as feedbackClient — an intent
 * breadcrumb before the call (so a network drop still leaves a trail)
 * and a result breadcrumb after.
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";
import {
  addApiBreadcrumb,
  addBreadcrumb,
} from "@/src/observability/breadcrumb";

export type ConsentType =
  | "terms_general"
  | "health_data_processing"
  | "push_notifications"
  | "summary_email";

export type RecordConsentInput = {
  device_id: string;
  consent_type: ConsentType;
  consent_version: string;
  granted: boolean;
  locale: string;
  notice_version?: string;
  session_id?: string;
};

export type RecordConsentResponse = {
  ok: boolean;
  id?: number;
  granted_at?: string;
};

const TIMEOUT_MS = 10000;

export async function recordConsent(
  input: RecordConsentInput,
): Promise<RecordConsentResponse> {
  addBreadcrumb(
    "consent",
    `submit intent type=${input.consent_type} granted=${input.granted}`,
    {
      consent_type: input.consent_type,
      consent_version: input.consent_version,
      granted: input.granted,
      locale: input.locale,
    },
    "info",
  );
  const startedAt = Date.now();
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/consent`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      },
      TIMEOUT_MS,
    );
    addApiBreadcrumb({
      endpoint: "/v1/consent",
      method: "POST",
      status: res.status,
      durationMs: Date.now() - startedAt,
      level: res.ok ? "info" : "error",
    });
    if (!res.ok) throw new Error("consent_failed");
    return (await res.json()) as RecordConsentResponse;
  } catch (err) {
    if (err instanceof Error && err.message === "consent_failed") {
      throw err;
    }
    addApiBreadcrumb({
      endpoint: "/v1/consent",
      method: "POST",
      status: 0,
      durationMs: Date.now() - startedAt,
      level: "error",
      note: err instanceof Error ? err.name : "network",
    });
    throw err;
  }
}

/**
 * Record both terms_general + health_data_processing in parallel.
 * The intro screen uses this; failing either fails the whole call so
 * the user retries (versus shipping with a half-recorded consent
 * which would be the worst possible audit-trail state).
 */
export async function recordIntroConsents(input: {
  device_id: string;
  locale: string;
  terms_version: string;
  health_data_version: string;
  notice_version?: string;
}): Promise<{ ok: true }> {
  await Promise.all([
    recordConsent({
      device_id: input.device_id,
      consent_type: "terms_general",
      consent_version: input.terms_version,
      granted: true,
      locale: input.locale,
      notice_version: input.notice_version,
    }),
    recordConsent({
      device_id: input.device_id,
      consent_type: "health_data_processing",
      consent_version: input.health_data_version,
      granted: true,
      locale: input.locale,
      notice_version: input.notice_version,
    }),
  ]);
  return { ok: true };
}
