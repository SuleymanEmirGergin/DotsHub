/**
 * triageClient contract test — the first real consumer of the MSW
 * stack. Future tests (feedback, summary, push-token) follow the same
 * shape: pin API_BASE via jest.mock, let default handlers respond,
 * override per-test for error-path coverage.
 *
 * Why start here: `triageTurn` owns the main user flow (every message
 * typed by the user goes through it). A silent regression in its
 * envelope parsing would ship broken triage to users without being
 * caught by a compile/TS check.
 */

import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";

// Pin the runtime config before importing the client — the module
// reads API_BASE at import time.
jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.test",
  USE_MOCK: false,
}));

// Stub side effects the real client triggers. Location access would
// pop a native permissions prompt; deviceId would hit AsyncStorage.
jest.mock("../../utils/location", () => ({
  getCurrentLocation: async () => null,
}));
jest.mock("../../utils/deviceId", () => ({
  getDeviceId: () => "device-test-abc",
}));

describe("triageClient", () => {
  it("returns a RESULT envelope on the happy path", async () => {
    const { triageTurn } = require("../../src/api/triageClient");

    const envelope = await triageTurn({
      session_id: "sess-1",
      user_message: "midem bulanıyor",
      turn_index: 0,
      locale: "tr-TR",
    });

    expect(envelope.type).toBe("RESULT");
    expect(envelope.payload.recommended_specialty.id).toBe("internal_gi");
    expect(envelope.payload.top_conditions.length).toBeGreaterThan(0);
    expect(envelope.payload.top_conditions[0].disease_label).toBe("Gastrit");
  });

  it("maps HTTP 429 to an ERROR envelope with RATE_LIMIT code", async () => {
    server.use(
      http.post("http://api.test/v1/triage/turn", () =>
        HttpResponse.json(
          { detail: "Rate limit exceeded", reset_in_sec: 42 },
          { status: 429 },
        ),
      ),
    );

    const { triageTurn } = require("../../src/api/triageClient");
    const envelope = await triageTurn({
      session_id: "sess-2",
      user_message: "hi",
      turn_index: 0,
      locale: "tr-TR",
    });

    expect(envelope.type).toBe("ERROR");
    expect(envelope.payload.code).toBe("RATE_LIMIT");
    // Turkish copy surfaces the retry window — don't pin the exact
    // wording (i18n tweaks shouldn't flake this), just the number.
    expect(envelope.payload.message_tr).toMatch(/42/);
  });

  it("maps HTTP 5xx to an ERROR envelope with HTTP_ERROR code", async () => {
    server.use(
      http.post("http://api.test/v1/triage/turn", () =>
        HttpResponse.json({ detail: "upstream down" }, { status: 502 }),
      ),
    );

    const { triageTurn } = require("../../src/api/triageClient");
    const envelope = await triageTurn({
      session_id: "sess-3",
      user_message: "hi",
      turn_index: 0,
      locale: "tr-TR",
    });

    expect(envelope.type).toBe("ERROR");
    expect(envelope.payload.code).toBe("HTTP_ERROR");
  });

  it("maps a network-layer failure to an ERROR envelope with NETWORK_ERROR code", async () => {
    // MSW's HttpResponse.error() simulates a fetch-layer failure
    // (e.g. DNS, TLS, socket reset) — distinct from an HTTP error.
    server.use(
      http.post("http://api.test/v1/triage/turn", () => HttpResponse.error()),
    );

    const { triageTurn } = require("../../src/api/triageClient");
    const envelope = await triageTurn({
      session_id: "sess-4",
      user_message: "hi",
      turn_index: 0,
      locale: "tr-TR",
    });

    expect(envelope.type).toBe("ERROR");
    expect(envelope.payload.code).toBe("NETWORK_ERROR");
  });

  it("forwards x-device-id header", async () => {
    let capturedDeviceId: string | null = null;
    server.use(
      http.post("http://api.test/v1/triage/turn", ({ request }) => {
        capturedDeviceId = request.headers.get("x-device-id");
        return HttpResponse.json({
          type: "QUESTION",
          session_id: "sess-5",
          turn_index: 1,
          payload: { question_tr: "ne zaman başladı?" },
        });
      }),
    );

    const { triageTurn } = require("../../src/api/triageClient");
    await triageTurn({
      session_id: "sess-5",
      user_message: "hi",
      turn_index: 0,
      locale: "tr-TR",
    });

    expect(capturedDeviceId).toBe("device-test-abc");
  });
});
