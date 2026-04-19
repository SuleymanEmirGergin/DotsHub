/**
 * featuresClient contract test — hits /v1/config/features through
 * MSW and asserts (a) the green-path shape includes the M4
 * client_version block, and (b) a backend that returns 500 or garbage
 * resolves to the safe default (enforcement_mode = "off"), not a
 * thrown error. A broken startup fetch must NEVER brick app launch.
 */

import { http, HttpResponse } from "msw";

import { server } from "../mocks/server";

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.test",
  USE_MOCK: false,
}));

describe("featuresClient", () => {
  it("returns the full FeaturesConfig on 200", async () => {
    server.use(
      http.get("http://api.test/v1/config/features", () =>
        HttpResponse.json({
          llm_nlu_enabled: true,
          llm_explain_enabled: false,
          client_version: {
            min: "1.2.0",
            latest: "1.3.5",
            mode: "warn",
            update_url_ios: "itms-apps://apple.com/app/id123",
            update_url_android: "market://details?id=com.dotshub",
          },
        }),
      ),
    );

    const { fetchFeatures } = require("../../src/api/featuresClient");
    const out = await fetchFeatures();

    expect(out.llm_nlu_enabled).toBe(true);
    expect(out.client_version.min).toBe("1.2.0");
    expect(out.client_version.mode).toBe("warn");
    expect(out.client_version.update_url_ios).toContain("apple.com");
  });

  it("falls back to safe defaults on HTTP 500", async () => {
    server.use(
      http.get("http://api.test/v1/config/features", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );

    const { fetchFeatures } = require("../../src/api/featuresClient");
    const out = await fetchFeatures();

    // Core invariant: startup fetch failure must NEVER lock the user
    // out. "off" means the version gate is silent.
    expect(out.client_version.mode).toBe("off");
    expect(out.client_version.min).toBe("0.0.0");
  });

  it("falls back to safe defaults on network error", async () => {
    server.use(
      http.get("http://api.test/v1/config/features", () =>
        HttpResponse.error(),
      ),
    );

    const { fetchFeatures } = require("../../src/api/featuresClient");
    const out = await fetchFeatures();

    expect(out.client_version.mode).toBe("off");
  });

  it("merges a partial payload from an older backend", async () => {
    // Pre-M4 backend doesn't carry the client_version block at all.
    // The client must defensively fill it in with defaults.
    server.use(
      http.get("http://api.test/v1/config/features", () =>
        HttpResponse.json({
          llm_nlu_enabled: true,
          llm_explain_enabled: true,
        }),
      ),
    );

    const { fetchFeatures } = require("../../src/api/featuresClient");
    const out = await fetchFeatures();

    expect(out.llm_nlu_enabled).toBe(true);
    expect(out.client_version).toBeDefined();
    expect(out.client_version.mode).toBe("off");
    expect(out.client_version.min).toBe("0.0.0");
  });
});
