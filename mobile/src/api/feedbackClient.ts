/**
 * Feedback API client — sends user rating (up/down) to backend.
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";

export async function sendFeedback(payload: {
  session_id: string;
  rating: "up" | "down";
  comment?: string | null;
  user_selected_specialty_id?: string | null;
}): Promise<{ ok: boolean }> {
  const res = await fetchWithTimeout(
    `${API_BASE}/v1/triage/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    10000,
  );
  if (!res.ok) throw new Error("feedback_failed");
  return (await res.json()) as { ok: boolean };
}
