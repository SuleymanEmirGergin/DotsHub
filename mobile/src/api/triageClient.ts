import { API_BASE, USE_MOCK } from "@/src/config/runtime";
import type { Envelope, TriageTurnRequest } from "@/src/state/types";
import { mockTurn } from "./mock/mockEngine";
import { fetchWithTimeout } from "./fetchWithTimeout";
import { getDeviceId } from "../../utils/deviceId";
import { getCurrentLocation } from "../../utils/location";

export async function triageTurn(req: TriageTurnRequest): Promise<Envelope> {
  if (USE_MOCK) return mockTurn(req);

  try {
    const location = req.lat != null && req.lon != null ? { lat: req.lat, lon: req.lon } : await getCurrentLocation();
    const deviceId = getDeviceId();
    // Send device_id both as body field (backend pydantic schema reads
    // it to persist on the session row for follow-up reminders) and
    // as header (still consumed by observability + rate-limit paths).
    const body: TriageTurnRequest & { device_id?: string } = { ...req, device_id: deviceId };
    if (location) {
      body.lat = location.lat;
      body.lon = location.lon;
    }
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/triage/turn`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-device-id": deviceId,
        },
        body: JSON.stringify(body),
      },
      12000,
    );

    if (!res.ok) {
      if (res.status === 429) {
        let resetSec = 60;
        try {
          const resetHeader = res.headers.get("X-RateLimit-Reset");
          if (resetHeader) resetSec = parseInt(resetHeader, 10) || 60;
          else {
            const data = await res.json().catch(() => ({}));
            if (typeof data?.reset_in_sec === "number") resetSec = data.reset_in_sec;
          }
        } catch {
          /* use default */
        }
        return {
          type: "ERROR",
          session_id: req.session_id ?? "unknown",
          turn_index: 0,
          payload: {
            code: "RATE_LIMIT",
            message_tr: `Çok fazla istek. ${resetSec} saniye sonra tekrar deneyin.`,
          },
        };
      }
      return {
        type: "ERROR",
        session_id: req.session_id ?? "unknown",
        turn_index: 0,
        payload: {
          code: "HTTP_ERROR",
          message_tr: `Sunucuya ulaşılamadı (${res.status}).`,
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
            ? "İstek zaman aşımına uğradı."
            : "Bağlantı hatası oluştu.",
      },
    };
  }
}
