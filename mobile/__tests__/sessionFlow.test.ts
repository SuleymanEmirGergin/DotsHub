/**
 * Session happy-path — verifies the MSW default handlers return the
 * envelope shape the UI relies on:
 *   start → QUESTION
 *   result → RESULT with urgency=ER_NOW and meta.facility_discovery (curated meta)
 *
 * Also covers an override case: tests can narrow the result to a different
 * urgency via `server.use()` without touching the default handler.
 */
import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.example.com",
}));

describe("session flow (MSW defaults)", () => {
  it("POST /session/start returns a QUESTION envelope", async () => {
    const { api } = require("../services/api");
    const env = await api.startSession("Göğsüm ağrıyor", { age: 45, sex: "M" });

    expect(env.type).toBe("QUESTION");
    expect(env.session_id).toBe("sess-msw-default");
    expect(env.payload.question_tr).toMatch(/Şikayetiniz/);
    expect(env.payload.answer_type).toBe("multiple_choice");
    expect(env.meta.disclaimer_tr).toContain("tıbbi tavsiye");
  });

  it("GET /session/{id}/result returns ER_NOW + curated facility_discovery meta", async () => {
    const { api } = require("../services/api");
    const env = await api.getResult("sess-42");

    expect(env.type).toBe("RESULT");
    expect(env.session_id).toBe("sess-42");
    expect(env.payload.urgency).toBe("ER_NOW");
    expect(env.payload.recommended_specialty_tr).toBe("Acil Tıp");
    expect(env.payload.candidates_tr.length).toBeGreaterThan(0);
    expect(env.meta.facility_discovery).toBeDefined();
    expect(env.meta.facility_discovery.specialty_id).toBe("emergency");
    expect(env.meta.facility_discovery.items[0].type).toBe("ER");
  });

  it("per-test override can narrow urgency to ROUTINE", async () => {
    server.use(
      http.get("*/v1/session/:sessionId/result", async ({ params }) => {
        return HttpResponse.json({
          type: "RESULT",
          session_id: String(params.sessionId),
          payload: {
            recommended_specialty_tr: "Dahiliye",
            urgency: "ROUTINE",
            candidates_tr: [],
            rationale_tr: [],
            emergency_watchouts_tr: [],
            doctor_ready_summary_tr: {
              symptoms_tr: [],
              timeline_tr: "",
              qa_highlights_tr: [],
              risk_level: "low",
            },
          },
          meta: {
            disclaimer_tr: "override",
            timestamp: "2026-04-18T10:00:00Z",
          },
        });
      }),
    );

    const { api } = require("../services/api");
    const env = await api.getResult("sess-override");

    expect(env.payload.urgency).toBe("ROUTINE");
    expect(env.meta.facility_discovery).toBeUndefined();
  });

  it("unhandled network call surfaces as an error (onUnhandledRequest)", async () => {
    server.use(
      http.get("*/v1/session/:sessionId/result", async () => {
        return HttpResponse.json({ detail: "not found" }, { status: 404 });
      }),
    );

    const { api } = require("../services/api");
    await expect(api.getResult("sess-404")).rejects.toThrow("not found");
  });
});
