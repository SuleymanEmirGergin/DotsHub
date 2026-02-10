import { API_BASE, USE_MOCK } from "@/src/config/runtime";
import type { Envelope, TriageTurnRequest } from "@/src/state/types";
import { mockTurn } from "./mock/mockEngine";
import { fetchWithTimeout } from "./fetchWithTimeout";

export async function triageTurn(req: TriageTurnRequest): Promise<Envelope> {
  if (USE_MOCK) return mockTurn(req);

  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/triage/turn`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      },
      12000,
    );

    if (!res.ok) {
      return {
        type: "ERROR",
        session_id: req.session_id ?? "unknown",
        turn_index: 0,
        payload: {
          code: "HTTP_ERROR",
          message_tr: `Sunucuya ulasilamadi (${res.status}).`,
        },
      };
    }

    return (await res.json()) as Envelope;
  } catch (err: any) {
    return {
      type: "ERROR",
      session_id: req.session_id ?? "unknown",
      turn_index: 0,
      payload: {
        code: "NETWORK_ERROR",
        message_tr:
          err?.name === "AbortError"
            ? "Istek zaman asimina ugradi."
            : "Baglanti hatasi olustu.",
      },
    };
  }
}
