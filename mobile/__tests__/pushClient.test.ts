jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.example.com",
}));

type CapturedCall = {
  url: string;
  method: string;
  body: string;
};

function installFetchMock(
  calls: CapturedCall[],
  response: { ok: boolean; status?: number; json: () => Promise<unknown> },
) {
  (globalThis as { fetch: typeof fetch }).fetch = (async (url, opts) => {
    calls.push({
      url: String(url),
      method: String(opts?.method ?? ""),
      body: String(opts?.body ?? ""),
    });
    return response as unknown as Response;
  }) as typeof fetch;
}

describe("pushClient", () => {
  const originalFetch = globalThis.fetch;

  afterAll(() => {
    (globalThis as { fetch: typeof fetch }).fetch = originalFetch;
  });

  it("registerPushToken posts expected payload", async () => {
    const calls: CapturedCall[] = [];
    installFetchMock(calls, {
      ok: true,
      json: async () => ({ ok: true }),
    });

    const { registerPushToken } = require("../src/api/pushClient");
    const out = await registerPushToken("ExponentPushToken[abc]", "device-1", "en");

    expect(JSON.stringify(out)).toBe(JSON.stringify({ ok: true }));
    expect(calls.length).toBe(1);
    expect(calls[0].url).toBe("http://api.example.com/v1/triage/push-token");
    expect(calls[0].method).toBe("POST");
    expect(
      JSON.stringify(JSON.parse(calls[0].body)),
    ).toBe(
      JSON.stringify({
        expo_push_token: "ExponentPushToken[abc]",
        device_id: "device-1",
        platform: "ios",
        locale: "en-US",
      }),
    );
  });

  it("registerPushToken falls back locale to tr-TR", async () => {
    const calls: CapturedCall[] = [];
    installFetchMock(calls, {
      ok: true,
      json: async () => ({ ok: true }),
    });

    const { registerPushToken } = require("../src/api/pushClient");
    await registerPushToken("ExponentPushToken[abc]", "device-2", "xx");

    const payload = JSON.parse(calls[0].body) as { locale: string };
    expect(payload.locale).toBe("tr-TR");
  });

  it("registerPushToken surfaces backend detail on failure", async () => {
    const calls: CapturedCall[] = [];
    installFetchMock(calls, {
      ok: false,
      status: 503,
      json: async () => ({ detail: "persist failed" }),
    });

    const { registerPushToken } = require("../src/api/pushClient");

    let message = "";
    try {
      await registerPushToken("ExponentPushToken[abc]", "device-3", "tr");
    } catch (err) {
      message = err instanceof Error ? err.message : String(err);
    }

    expect(message).toBe("persist failed");
  });

  it("unregisterPushToken sends delete with device id", async () => {
    const calls: CapturedCall[] = [];
    installFetchMock(calls, {
      ok: true,
      json: async () => ({ ok: true }),
    });

    const { unregisterPushToken } = require("../src/api/pushClient");
    const out = await unregisterPushToken("device-9");

    expect(JSON.stringify(out)).toBe(JSON.stringify({ ok: true }));
    expect(calls.length).toBe(1);
    expect(calls[0].url).toBe("http://api.example.com/v1/triage/push-token");
    expect(calls[0].method).toBe("DELETE");
    expect(JSON.stringify(JSON.parse(calls[0].body))).toBe(
      JSON.stringify({ device_id: "device-9" }),
    );
  });

  it("unregisterPushToken returns fallback message when response is not json", async () => {
    const calls: CapturedCall[] = [];
    installFetchMock(calls, {
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("invalid json");
      },
    });

    const { unregisterPushToken } = require("../src/api/pushClient");

    let message = "";
    try {
      await unregisterPushToken("device-10");
    } catch (err) {
      message = err instanceof Error ? err.message : String(err);
    }

    expect(message).toBe("Unregister failed (HTTP 500)");
  });
});
