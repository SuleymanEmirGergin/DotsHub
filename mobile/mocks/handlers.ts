/**
 * MSW request handlers — mobile test suite.
 *
 * Host-agnostic ("*" prefix) so tests can mock `@/src/config/runtime`
 * to any API_BASE (e.g. `http://api.example.com`) without changing handlers.
 *
 * Default responses target the golden path. Individual tests can override
 * via `server.use(...)` in `mocks/server.ts`.
 */
import { http, HttpResponse } from "msw";

// ─── Default fixtures ───

const DEFAULT_DISCLAIMER_TR =
  "Bu bilgi tıbbi tavsiye değildir; acil durumda 112'yi arayın.";
const DEFAULT_TIMESTAMP = "2026-04-18T10:00:00Z";

const DEFAULT_META = {
  disclaimer_tr: DEFAULT_DISCLAIMER_TR,
  timestamp: DEFAULT_TIMESTAMP,
  model_info: { name: "mock", version: "test" },
  debug: {},
};

// Golden-path session ID used when no explicit id supplied
const DEFAULT_SESSION_ID = "sess-msw-default";

// ─── Handlers ───

export const handlers = [
  // POST /v1/session/start → QUESTION envelope
  http.post("*/v1/session/start", async () => {
    return HttpResponse.json({
      type: "QUESTION",
      session_id: DEFAULT_SESSION_ID,
      payload: {
        question_tr: "Şikayetiniz ne zaman başladı?",
        answer_type: "multiple_choice",
        choices_tr: ["Bugün", "Dün", "Bir haftadan uzun"],
        ui_hints: { quick_replies: true },
      },
      meta: DEFAULT_META,
    });
  }),

  // POST /v1/session/{id}/message → QUESTION (follow-up) envelope
  http.post("*/v1/session/:sessionId/message", async ({ params }) => {
    return HttpResponse.json({
      type: "QUESTION",
      session_id: String(params.sessionId),
      payload: {
        question_tr: "Ağrı şiddeti nasıl?",
        answer_type: "number",
        choices_tr: [],
        ui_hints: {},
      },
      meta: DEFAULT_META,
    });
  }),

  // GET /v1/session/{id}/result → RESULT (ER_NOW + curated meta)
  http.get("*/v1/session/:sessionId/result", async ({ params }) => {
    return HttpResponse.json({
      type: "RESULT",
      session_id: String(params.sessionId),
      payload: {
        recommended_specialty_tr: "Acil Tıp",
        urgency: "ER_NOW",
        candidates_tr: [
          {
            label_tr: "Akut koroner sendrom şüphesi",
            probability_0_1: 0.72,
            supporting_evidence_tr: ["göğüs ağrısı", "sol kola yayılım"],
            contradicting_evidence_tr: [],
          },
        ],
        rationale_tr: ["ER_NOW: ani başlangıç göğüs ağrısı + yayılım"],
        emergency_watchouts_tr: ["bilinç kaybı", "nefes darlığı artışı"],
        doctor_ready_summary_tr: {
          symptoms_tr: ["göğüs ağrısı", "sol kola yayılım"],
          timeline_tr: "30 dk önce başladı, devam ediyor",
          qa_highlights_tr: ["Ağrı baskı/sıkışma tipinde"],
          risk_level: "high",
        },
        specialty_scores: { cardiology: 0.81, emergency: 0.92 },
      },
      meta: {
        ...DEFAULT_META,
        facility_discovery: {
          specialty_id: "emergency",
          city: "Istanbul",
          items: [
            {
              name: "Mock Acil Servisi",
              type: "ER",
              address: "Test Mah. 1",
              distance_km: 1.2,
            },
          ],
          disclaimer: "Konum verisi test amaçlıdır.",
        },
      },
    });
  }),

  // GET /v1/session/{id}/summary → SummaryResponse
  http.get("*/v1/session/:sessionId/summary", async ({ params }) => {
    return HttpResponse.json({
      session_id: String(params.sessionId),
      doctor_ready_summary_tr: {
        symptoms_tr: ["göğüs ağrısı"],
        timeline_tr: "30 dk",
        qa_highlights_tr: ["baskı/sıkışma tipi"],
        risk_level: "high",
      },
      candidates: [],
      routing: {
        recommended_specialty_tr: "Acil Tıp",
        urgency: "ER_NOW",
        rationale_tr: ["ER_NOW kriterleri karşılandı"],
        emergency_watchouts_tr: [],
        doctor_ready_summary_tr: {
          symptoms_tr: ["göğüs ağrısı"],
          timeline_tr: "30 dk",
          qa_highlights_tr: [],
          risk_level: "high",
        },
      },
      messages: [],
      disclaimer: DEFAULT_DISCLAIMER_TR,
    });
  }),

  // GET /v1/session/{id}/state (debug) → opaque object
  http.get("*/v1/session/:sessionId/state", async ({ params }) => {
    return HttpResponse.json({
      session_id: String(params.sessionId),
      debug: { turn_count: 3 },
    });
  }),

  // POST /v1/triage/push-token → ok
  http.post("*/v1/triage/push-token", async () => {
    return HttpResponse.json({ ok: true });
  }),

  // DELETE /v1/triage/push-token → ok
  http.delete("*/v1/triage/push-token", async () => {
    return HttpResponse.json({ ok: true });
  }),
];
