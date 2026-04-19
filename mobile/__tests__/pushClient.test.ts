/**
 * pushClient tests — MSW-based (handler intercepts in mocks/server).
 *
 * Per-test `server.use()` overrides capture the outgoing request
 * (URL, method, body) so we can assert the wire format without
 * manually stubbing `globalThis.fetch`.
 */
import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";

jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.example.com",
}));

type Captured = {
  method: string;
  url: string;
  body: unknown;
};

describe("pushClient", () => {
  it("registerPushToken posts expected payload", async () => {
    let captured: Captured | null = null;
    server.use(
      http.post("*/v1/triage/push-token", async ({ request }) => {
        captured = {
          method: request.method,
          url: request.url,
          body: await request.json(),
        };
        return HttpResponse.json({ ok: true });
      }),
    );

    const { registerPushToken } = require("../src/api/pushClient");
    const out = await registerPushToken("ExponentPushToken[abc]", "device-1", "en");

    expect(out).toEqual({ ok: true });
    expect(captured).not.toBeNull();
    expect(captured!.method).toBe("POST");
    expect(captured!.url).toBe("http://api.example.com/v1/triage/push-token");
    expect(captured!.body).toEqual({
      expo_push_token: "ExponentPushToken[abc]",
      device_id: "device-1",
      platform: "ios",
      locale: "en-US",
    });
  });

  it("registerPushToken falls back locale to tr-TR", async () => {
    let capturedBody: { locale?: string } | null = null;
    server.use(
      http.post("*/v1/triage/push-token", async ({ request }) => {
        capturedBody = (await request.json()) as { locale?: string };
        return HttpResponse.json({ ok: true });
      }),
    );

    const { registerPushToken } = require("../src/api/pushClient");
    await registerPushToken("ExponentPushToken[abc]", "device-2", "xx");

    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.locale).toBe("tr-TR");
  });

  it("registerPushToken surfaces backend detail on failure", async () => {
    server.use(
      http.post("*/v1/triage/push-token", async () => {
        return HttpResponse.json({ detail: "persist failed" }, { status: 503 });
      }),
    );

    const { registerPushToken } = require("../src/api/pushClient");
    await expect(
      registerPushToken("ExponentPushToken[abc]", "device-3", "tr"),
    ).rejects.toThrow("persist failed");
  });

  it("unregisterPushToken sends delete with device id", async () => {
    let captured: Captured | null = null;
    server.use(
      http.delete("*/v1/triage/push-token", async ({ request }) => {
        captured = {
          method: request.method,
          url: request.url,
          body: await request.json(),
        };
        return HttpResponse.json({ ok: true });
      }),
    );

    const { unregisterPushToken } = require("../src/api/pushClient");
    const out = await unregisterPushToken("device-9");

    expect(out).toEqual({ ok: true });
    expect(captured).not.toBeNull();
    expect(captured!.method).toBe("DELETE");
    expect(captured!.url).toBe("http://api.example.com/v1/triage/push-token");
    expect(captured!.body).toEqual({ device_id: "device-9" });
  });

  it("unregisterPushToken returns fallback message when response is not json", async () => {
    server.use(
      http.delete("*/v1/triage/push-token", async () => {
        return new HttpResponse("not json", {
          status: 500,
          headers: { "Content-Type": "text/plain" },
        });
      }),
    );

    const { unregisterPushToken } = require("../src/api/pushClient");
    await expect(unregisterPushToken("device-10")).rejects.toThrow(
      "Unregister failed (HTTP 500)",
    );
  });
});
