/**
 * Summary email and export API — POST /v1/triage/send-summary, POST /v1/triage/export-summary
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";
import type { ResultPayload } from "@/src/state/types";

const BASE = `${API_BASE}/v1/triage`;

/**
 * POST /v1/triage/send-summary
 * Body: { session_id, email, locale }
 * Backend accepts tr | en | de | ru | ar (de/ru/ar use Turkish content).
 */
export async function sendSummaryEmail(
  sessionId: string,
  email: string,
  locale: string = "tr",
): Promise<{ status: string; message: string }> {
  const res = await fetchWithTimeout(
    `${BASE}/send-summary`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, email, locale }),
    },
    15000,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Send failed" }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as { status: string; message: string };
}

/**
 * POST /v1/triage/export-summary
 * Body: { payload: ResultPayload, locale }
 * Returns: text/plain body
 */
export async function exportSummary(
  payload: ResultPayload,
  locale: string = "tr-TR",
): Promise<string> {
  const res = await fetchWithTimeout(
    `${BASE}/export-summary`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload, locale }),
    },
    10000,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Export failed" }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.text();
}
