/**
 * Default MSW handlers — green-path responses for the five backend
 * endpoints the mobile app hits.
 *
 * Per-test overrides go via server.use(http.post(..., handler)) in
 * the test body. Anything not listed here will miss and MSW will
 * warn (onUnhandledRequest: "warn" in jest.setup.js), so new
 * endpoints surface as test-time failures rather than silent
 * network calls.
 *
 * API_BASE is deliberately not read from runtime — the tests pin it
 * via jest.mock("@/src/config/runtime") so handlers can use a
 * fixed base URL. See __tests__/api/triageClient.test.ts for the
 * mock pattern.
 */

import { http, HttpResponse } from "msw";

const API_BASE = "http://api.test";

const ok = <T>(body: T) => HttpResponse.json(body, { status: 200 });

export const handlers = [
  // ── Triage turn ──────────────────────────────────────────────────
  http.post(`${API_BASE}/v1/triage/turn`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    // Default: return a single-turn RESULT with a plausible specialty.
    return ok({
      type: "RESULT",
      session_id: body.session_id ?? "sess-test",
      turn_index: 1,
      payload: {
        recommended_specialty: { id: "internal_gi", tr: "Dahiliye" },
        confidence_0_1: 0.82,
        top_conditions: [
          {
            disease_label: "Gastrit",
            score_0_1: 0.67,
            source_type: "curated",
            disease_description: "Mide astarının iltihabı.",
            ipucu_tr: "Boş mideye kahve azaltın.",
          },
        ],
        doctor_ready_summary_tr: "Son 3 gündür mide ağrısı ve bulantı.",
        disclaimer_tr:
          "Bu liste tanı değildir, yalnızca hazırlık amaçlıdır.",
      },
    });
  }),

  // ── Feedback ─────────────────────────────────────────────────────
  http.post(`${API_BASE}/v1/triage/feedback`, () => ok({ ok: true })),

  // ── Send summary email ───────────────────────────────────────────
  http.post(`${API_BASE}/v1/triage/send-summary`, () => ok({ ok: true })),

  // ── Export summary PDF ───────────────────────────────────────────
  http.post(`${API_BASE}/v1/triage/export-summary`, () =>
    HttpResponse.text("PDF-BYTES", {
      status: 200,
      headers: { "Content-Type": "application/pdf" },
    }),
  ),

  // ── Push token ───────────────────────────────────────────────────
  http.post(`${API_BASE}/v1/triage/push-token`, () => ok({ ok: true })),
  http.delete(`${API_BASE}/v1/triage/push-token`, () => ok({ ok: true })),

  // ── Data rights (KVKK) ───────────────────────────────────────────
  http.delete(
    `${API_BASE}/v1/me/sessions/:session_id`,
    ({ params }) =>
      ok({
        ok: true,
        session_id: params.session_id,
        derived_deleted: { triage_events: 3, llm_calls: 2, triage_feedback: 1 },
      }),
  ),

  // ── Feature flags / version gate (M4) ────────────────────────────
  http.get(`${API_BASE}/v1/config/features`, () =>
    ok({
      llm_nlu_enabled: false,
      llm_explain_enabled: false,
      client_version: {
        min: "0.0.0",
        latest: "0.0.0",
        mode: "off",
        update_url_ios: null,
        update_url_android: null,
      },
    }),
  ),
];
