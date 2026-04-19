/**
 * Feedback client contract test — less critical than triage, but it's
 * the only user-facing way we learn whether a recommendation was
 * helpful. A silent 4xx here means we'd ship "your feedback was
 * saved" while actually dropping it.
 */

import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.test",
  USE_MOCK: false,
}));

jest.mock("../../utils/deviceId", () => ({
  getDeviceId: () => "device-fb-test",
}));

describe("feedbackClient", () => {
  it("posts a 'down' rating and returns ok on 200", async () => {
    let body: any = null;
    server.use(
      http.post("http://api.test/v1/triage/feedback", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );

    const { sendFeedback } = require("../../src/api/feedbackClient");
    const out = await sendFeedback({
      session_id: "sess-f1",
      rating: "down",
      comment: "Yanlış branş",
    });

    expect(out).toEqual({ ok: true });
    expect(body.session_id).toBe("sess-f1");
    expect(body.rating).toBe("down");
    expect(body.comment).toBe("Yanlış branş");
  });

  it("throws feedback_failed on 4xx/5xx", async () => {
    server.use(
      http.post("http://api.test/v1/triage/feedback", () =>
        HttpResponse.json({ detail: "session not found" }, { status: 404 }),
      ),
    );

    const { sendFeedback } = require("../../src/api/feedbackClient");
    let msg = "";
    try {
      await sendFeedback({
        session_id: "sess-missing",
        rating: "up",
      });
    } catch (err) {
      msg = err instanceof Error ? err.message : String(err);
    }
    // Client intentionally doesn't surface the backend detail —
    // the UI shows a generic toast. Assert the contract is stable.
    expect(msg).toBe("feedback_failed");
  });
});
