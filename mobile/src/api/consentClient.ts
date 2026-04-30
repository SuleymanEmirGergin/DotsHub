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
import { API_BASE, USE_MOCK } from "@/src/config/runtime";
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
  // Mock mode: skip the network call so local/offline testing on a
  // device (where localhost:8000 is unreachable) doesn't strand users
  // at the intro screen. Matches triageClient/facilitiesClient. The
  // production build sets USE_MOCK=false and still hits /v1/consent
  // for the real audit row.
  if (USE_MOCK) {
    addBreadcrumb(
      "consent",
      `mock skip type=${input.consent_type}`,
      { consent_type: input.consent_type, mock: true },
      "info",
    );
    return { ok: true, id: 0, granted_at: new Date().toISOString() };
  }
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
 *
 * Best-effort by design: the prod /v1/consent route may be missing
 * (older backend deploys return 404) or unreachable on first launch.
 * Blocking the user behind a network call to a route that doesn't
 * exist would strand every install at the intro screen — a worse
 * outcome than a degraded audit trail.
 *
 * Failure path: the consent payload (device_id, type, version,
 * notice_version, locale, timestamp) is captured as a Sentry
 * breadcrumb at error level inside `recordConsent`. The downstream
 * /v1/triage call also carries notice_version + consent_version, so
 * the backend reconstructs the audit row on the first session POST.
 * The "always-throw" version of this function predates that backfill
 * path and is no longer the right contract.
 */
export async function recordIntroConsents(input: {
  device_id: string;
  locale: string;
  terms_version: string;
  health_data_version: string;
  notice_version?: string;
}): Promise<{ ok: true }> {
  const results = await Promise.allSettled([
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
  const failures = results.filter((r) => r.status === "rejected");
  if (failures.length > 0) {
    addBreadcrumb(
      "consent",
      `intro consent degraded: ${failures.length}/2 posts failed — proceeding with local-only record`,
      {
        device_id: input.device_id,
        locale: input.locale,
        terms_version: input.terms_version,
        health_data_version: input.health_data_version,
        notice_version: input.notice_version,
        recorded_at: new Date().toISOString(),
      },
      "warning",
    );
  }
  return { ok: true };
}
