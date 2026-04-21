/**
 * Feedback API client — sends user rating (up/down) to backend.
 *
 * Breadcrumbs: we emit an `api` breadcrumb per call with the rating
 * value in `data`. A "user reports the result was wrong" bug report
 * is useless without knowing which rating the client sent — the
 * breadcrumb trail gives us that without needing the full PII-scrubbed
 * body.
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";
import {
  addApiBreadcrumb,
  addBreadcrumb,
} from "@/src/observability/breadcrumb";

export async function sendFeedback(payload: {
  session_id: string;
  rating: "up" | "down";
  comment?: string | null;
  user_selected_specialty_id?: string | null;
}): Promise<{ ok: boolean }> {
  // Record the user's INTENT as a separate breadcrumb category before
  // the HTTP call fires. Useful when the call never returns (network
  // drop) — the feedback intent is still in the trail.
  addBreadcrumb(
    "feedback",
    `submit intent rating=${payload.rating}`,
    {
      rating: payload.rating,
      has_comment: Boolean(payload.comment && payload.comment.trim()),
    },
    "info",
  );
  const startedAt = Date.now();
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/triage/feedback`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      10000,
    );
    addApiBreadcrumb({
      endpoint: "/v1/triage/feedback",
      method: "POST",
      status: res.status,
      durationMs: Date.now() - startedAt,
      level: res.ok ? "info" : "error",
    });
    if (!res.ok) throw new Error("feedback_failed");
    return (await res.json()) as { ok: boolean };
  } catch (err) {
    // Distinguish network drop (status=0) from HTTP error — the
    // try/catch treats both the same, but the breadcrumb status
    // field tells ops which.
    if (err instanceof Error && err.message === "feedback_failed") {
      // HTTP error already logged above; just rethrow.
      throw err;
    }
    addApiBreadcrumb({
      endpoint: "/v1/triage/feedback",
      method: "POST",
      status: 0,
      durationMs: Date.now() - startedAt,
      level: "error",
      note: err instanceof Error ? err.name : "network",
    });
    throw err;
  }
}
