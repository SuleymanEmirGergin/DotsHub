/**
 * quoteClient HTTP contract test (Session 17 health-tourism pivot).
 *
 * Same MSW pattern as the triageClient contract: pin API_BASE,
 * intercept the network call, capture the outgoing request, then
 * assert the wire shape we promise the backend.
 *
 * Why pin this contract:
 *   - Backend's idempotency layer requires `Idempotency-Key`. Forgetting
 *     to send it returns the user a different price every retry — the
 *     bug the backend layer was specifically built to fix.
 *   - `x-device-id` is read by the rate-limit + observability paths;
 *     missing it lumps the entire app under a single bucket.
 *   - The body shape (camelCase vs snake_case, optional vs required)
 *     drifts often when shared catalogs change.
 */

import { http, HttpResponse } from "msw";
import { server } from "../../mocks/server";

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.test",
  USE_MOCK: false,
}));
jest.mock("../../utils/deviceId", () => ({
  getDeviceId: () => "device-test-abc",
}));
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));
jest.mock("../../src/observability/breadcrumb", () => ({
  addApiBreadcrumb: () => undefined,
}));

type Captured = {
  method: string;
  url: string;
  headers: Record<string, string>;
  body: any;
};

function captureNext<TBody>(path: string, replyJson: TBody) {
  let captured: Captured | null = null;
  server.use(
    http.post(`*${path}`, async ({ request }) => {
      captured = {
        method: request.method,
        url: request.url,
        headers: Object.fromEntries(request.headers),
        body: await request.json().catch(() => null),
      };
      return HttpResponse.json(replyJson as Record<string, unknown>);
    }),
  );
  return () => captured;
}

const QUOTE_ENVELOPE = {
  type: "QUOTE",
  session_id: "S_test",
  turn_index: 0,
  payload: {
    quote_id: "q_abc",
    procedure: { id: "fue_hair_transplant", name_tr: "FUE Saç Ekimi" },
    clinics: [],
    fit_to_travel_warnings: [],
    currency: "EUR",
    summary_tr: null,
  },
};

describe("quoteClient", () => {
  describe("requestQuote", () => {
    it("POSTs /v1/quote with idempotency + device headers", async () => {
      const get = captureNext("/v1/quote", QUOTE_ENVELOPE);
      const { requestQuote } = require("../../src/api/quoteClient");

      const env = await requestQuote({
        procedure_id: "fue_hair_transplant",
        profile: { recent_mi: false },
        locale: "tr-TR",
        top_n: 5,
      });

      expect(env.type).toBe("QUOTE");
      const c = get();
      expect(c).not.toBeNull();
      expect(c!.method).toBe("POST");
      expect(c!.headers["x-device-id"]).toBe("device-test-abc");
      // Idempotency-Key is required for retry-safe semantics.
      expect(c!.headers["idempotency-key"]).toBeDefined();
      expect(c!.headers["idempotency-key"]?.length).toBeGreaterThan(8);
      expect(c!.body.procedure_id).toBe("fue_hair_transplant");
      expect(c!.body.locale).toBe("tr-TR");
      expect(c!.body.top_n).toBe(5);
    });

    it("forwards x-session-id header when caller passes a sessionId", async () => {
      const get = captureNext("/v1/quote", QUOTE_ENVELOPE);
      const { requestQuote } = require("../../src/api/quoteClient");

      await requestQuote(
        { procedure_id: "fue_hair_transplant" },
        "S_existing",
      );
      const c = get();
      expect(c!.headers["x-session-id"]).toBe("S_existing");
    });

    it("returns ERROR envelope on 500", async () => {
      server.use(
        http.post("*/v1/quote", () => HttpResponse.json({}, { status: 500 })),
      );
      const { requestQuote } = require("../../src/api/quoteClient");
      const env = await requestQuote({ procedure_id: "fue_hair_transplant" });
      expect(env.type).toBe("ERROR");
      if (env.type === "ERROR") {
        expect(env.payload.code).toBe("HTTP_ERROR");
      }
    });

    it("returns RATE_LIMIT ERROR on 429", async () => {
      server.use(
        http.post("*/v1/quote", () =>
          HttpResponse.json(
            { reset_in_sec: 30 },
            { status: 429, headers: { "X-RateLimit-Reset": "30" } },
          ),
        ),
      );
      const { requestQuote } = require("../../src/api/quoteClient");
      const env = await requestQuote({ procedure_id: "fue_hair_transplant" });
      expect(env.type).toBe("ERROR");
      if (env.type === "ERROR") {
        expect(env.payload.code).toBe("RATE_LIMIT");
        expect(env.payload.message_tr).toMatch(/30/);
      }
    });
  });

  describe("requestItinerary", () => {
    it("POSTs /v1/quote/itinerary with all required fields", async () => {
      const replyEnv = {
        type: "ITINERARY",
        session_id: "S",
        turn_index: 0,
        payload: {
          procedure_id: "fue_hair_transplant",
          procedure_name_tr: "FUE",
          clinic_id: "c1",
          clinic_name: "X",
          clinic_city: "İstanbul",
          arrival_date: "2026-05-15",
          departure_date: "2026-05-18",
          total_days: 4,
          items: [],
          pre_op_requirements: [],
          post_op_no_fly_days: 3,
          post_op_followup_window_days: 14,
          fit_to_travel_warnings: [],
        },
      };
      const get = captureNext("/v1/quote/itinerary", replyEnv);
      const { requestItinerary } = require("../../src/api/quoteClient");

      const env = await requestItinerary({
        procedure_id: "fue_hair_transplant",
        clinic_id: "c1",
        arrival_date: "2026-05-15",
      });
      expect(env.type).toBe("ITINERARY");
      const c = get();
      expect(c!.body.procedure_id).toBe("fue_hair_transplant");
      expect(c!.body.clinic_id).toBe("c1");
      expect(c!.body.arrival_date).toBe("2026-05-15");
      expect(c!.headers["idempotency-key"]).toBeDefined();
    });
  });

  describe("submitLead", () => {
    it("POSTs /v1/quote/lead carrying KVKK consent + contact + quote_id", async () => {
      const replyEnv = {
        type: "RESULT",
        session_id: "S",
        turn_index: 0,
        payload: {
          code: "LEAD_ACCEPTED",
          lead_id: "lead_xyz",
          consent_to_share: true,
          webhook_status: "scheduled",
          webhook_configured: true,
          persisted: true,
          next_steps_tr: "ok",
          procedure_id: "p1",
          procedure_name_tr: "X",
          clinic_id: "c1",
          clinic_name: "Y",
        },
      };
      const get = captureNext("/v1/quote/lead", replyEnv);
      const { submitLead } = require("../../src/api/quoteClient");

      const env = await submitLead({
        procedure_id: "p1",
        clinic_id: "c1",
        contact: {
          name: "Ali",
          email: "ali@x.com",
          phone: "+9012",
          preferred_contact: "any",
        },
        consent_to_share: true,
        locale: "tr-TR",
        notes: "morning",
        quote_id: "q_abc",
      });
      expect(env.type).toBe("RESULT");
      const c = get();
      expect(c!.body.consent_to_share).toBe(true);
      expect(c!.body.contact.name).toBe("Ali");
      expect(c!.body.contact.email).toBe("ali@x.com");
      expect(c!.body.quote_id).toBe("q_abc");
    });
  });
});
