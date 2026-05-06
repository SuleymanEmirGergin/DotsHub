/**
 * Health-tourism API client (Session 17 pivot).
 *
 *   POST /v1/quote            — rank clinics, return QUOTE envelope
 *   POST /v1/quote/itinerary  — day-by-day plan (ITINERARY envelope)
 *   POST /v1/quote/lead       — patient accepts → CRM webhook (RESULT envelope)
 *
 * Shape and error semantics mirror triageClient.ts:
 *   - 429 → ERROR envelope with retry hint
 *   - non-2xx → ERROR envelope with HTTP_ERROR
 *   - timeout / network → ERROR envelope with NETWORK_ERROR
 *   - USE_MOCK=true → returns a deterministic in-process mock
 *
 * Idempotency: every call sends an `Idempotency-Key` header (UUID per
 * call). Backend caches QUOTE/ITINERARY/LEAD responses for 15 min on
 * the (tenant, device, key, body) tuple — same key + same body retry
 * returns the cached envelope, same key + different body returns 409.
 */

import { API_BASE, USE_MOCK } from "@/src/config/runtime";
import { fetchWithTimeout } from "./fetchWithTimeout";
import { getDeviceId } from "../../utils/deviceId";
import { addApiBreadcrumb } from "@/src/observability/breadcrumb";
import type {
  HtEnvelope,
  ItineraryRequest,
  LeadRequest,
  QuoteRequest,
} from "@/src/state/htTypes";
import { mockQuote, mockItinerary, mockLead } from "./mock/htMock";

function randomKey(): string {
  // Avoid pulling in a uuid lib — Math.random + Date.now is plenty
  // unique for the 15-min idempotency window.
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

async function postEnvelope<TReq>(
  path: string,
  body: TReq,
  timeoutMs: number,
  sessionId: string | null,
): Promise<HtEnvelope> {
  const startedAt = Date.now();
  const deviceId = getDeviceId();
  const idemKey = randomKey();

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "x-device-id": deviceId,
      "Idempotency-Key": idemKey,
    };
    if (sessionId) headers["x-session-id"] = sessionId;

    const res = await fetchWithTimeout(
      `${API_BASE}${path}`,
      { method: "POST", headers, body: JSON.stringify(body) },
      timeoutMs,
    );

    if (!res.ok) {
      const level = res.status === 429 ? "warning" : "error";
      addApiBreadcrumb({
        endpoint: path,
        method: "POST",
        status: res.status,
        durationMs: Date.now() - startedAt,
        level,
      });
      if (res.status === 429) {
        let resetSec = 60;
        try {
          const resetHeader = res.headers.get("X-RateLimit-Reset");
          if (resetHeader) resetSec = parseInt(resetHeader, 10) || 60;
        } catch {
          /* default */
        }
        return {
          type: "ERROR",
          session_id: sessionId ?? "unknown",
          turn_index: 0,
          payload: {
            code: "RATE_LIMIT",
            message_tr: `Çok fazla istek. ${resetSec} saniye sonra tekrar deneyin.`,
            retryable: true,
          },
        };
      }
      return {
        type: "ERROR",
        session_id: sessionId ?? "unknown",
        turn_index: 0,
        payload: {
          code: "HTTP_ERROR",
          message_tr: `Sunucuya ulaşılamadı (${res.status}).`,
          retryable: true,
        },
      };
    }

    addApiBreadcrumb({
      endpoint: path,
      method: "POST",
      status: res.status,
      durationMs: Date.now() - startedAt,
      level: "info",
    });
    return (await res.json()) as HtEnvelope;
  } catch (err: any) {
    addApiBreadcrumb({
      endpoint: path,
      method: "POST",
      status: 0,
      durationMs: Date.now() - startedAt,
      level: "error",
      note: err?.name ?? "network",
    });
    return {
      type: "ERROR",
      session_id: sessionId ?? "unknown",
      turn_index: 0,
      payload: {
        code: "NETWORK_ERROR",
        message_tr:
          err?.name === "AbortError"
            ? "İstek zaman aşımına uğradı."
            : "Bağlantı hatası oluştu.",
        retryable: true,
      },
    };
  }
}

// ─── Public API ────────────────────────────────────────────────────

export async function requestQuote(
  req: QuoteRequest,
  sessionId: string | null = null,
): Promise<HtEnvelope> {
  if (USE_MOCK) return mockQuote(req);
  // Quote pipeline runs procedure_intent + fit-to-travel + clinic ranking
  // + optional summary_tr cache lookup. Sometimes 5-8s, plus typical
  // network latency. 15s timeout matches the backend's idempotency TTL.
  return postEnvelope("/v1/quote", req, 15000, sessionId);
}

export async function requestItinerary(
  req: ItineraryRequest,
  sessionId: string | null = null,
): Promise<HtEnvelope> {
  if (USE_MOCK) return mockItinerary(req);
  return postEnvelope("/v1/quote/itinerary", req, 12000, sessionId);
}

export async function submitLead(
  req: LeadRequest,
  sessionId: string | null = null,
): Promise<HtEnvelope> {
  if (USE_MOCK) return mockLead(req);
  // Backend persists then schedules webhook; HTTP response is synchronous.
  return postEnvelope("/v1/quote/lead", req, 10000, sessionId);
}
