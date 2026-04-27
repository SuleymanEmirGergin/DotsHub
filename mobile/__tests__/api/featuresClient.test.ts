/**
 * featuresClient contract test — hits /v1/config/features through
 * MSW and asserts (a) the green-path shape includes the M4
 * client_version block, and (b) a backend that returns 500 or garbage
 * resolves to the safe default (enforcement_mode = "off"), not a
 * thrown error. A broken startup fetch must NEVER brick app launch.
 */

import { http, HttpResponse } from "msw";

import { server } from "../../mocks/server";

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
            update_url_android: "market://details?id=com.triaige",
          },
          consent: {
            notice_version: "v0.3",
            versions: {
              terms_general: "v1.1",
              health_data_processing: "v1.2",
              push_notifications: "v1.0",
              summary_email: "v1.0",
            },
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
    // The mobile intro screen reads these to drive consent records;
    // a backend bump must surface here.
    expect(out.consent.notice_version).toBe("v0.3");
    expect(out.consent.versions.health_data_processing).toBe("v1.2");
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
    // Pre-session-24 backend doesn't carry the consent block.
    // The client must defensively fill both in with defaults so
    // intro screen still has versions to record.
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
    // Consent defaults match the mobile build's hardcoded fallback —
    // first-launch-offline still has a usable version to send with
    // the audit row.
    expect(out.consent).toBeDefined();
    expect(out.consent.notice_version).toBe("v0.2");
    expect(out.consent.versions.terms_general).toBe("v1.0");
    expect(out.consent.versions.health_data_processing).toBe("v1.0");
  });

  it("falls back to default consent on HTTP 500 — no thrown error", async () => {
    server.use(
      http.get("http://api.test/v1/config/features", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );

    const { fetchFeatures } = require("../../src/api/featuresClient");
    const out = await fetchFeatures();

    // Intro screen reads consent off this; failure must not block
    // first launch.
    expect(out.consent.notice_version).toBe("v0.2");
    expect(out.consent.versions.health_data_processing).toBe("v1.0");
  });

  it("merges a backend that surfaces consent but only one version field", async () => {
    // A backend that bumped only health_data_processing should leave
    // the other three at their mobile defaults — not zero them out.
    server.use(
      http.get("http://api.test/v1/config/features", () =>
        HttpResponse.json({
          llm_nlu_enabled: false,
          llm_explain_enabled: false,
          client_version: {
            min: "0.0.0",
            latest: "0.0.0",
            mode: "off",
            update_url_ios: null,
            update_url_android: null,
          },
          consent: {
            notice_version: "v0.5",
            versions: {
              health_data_processing: "v2.0",
              // terms_general / push_notifications / summary_email
              // intentionally absent — older mobile build expects
              // them to remain at the default.
            },
          },
        }),
      ),
    );

    const { fetchFeatures } = require("../../src/api/featuresClient");
    const out = await fetchFeatures();

    expect(out.consent.notice_version).toBe("v0.5");
    expect(out.consent.versions.health_data_processing).toBe("v2.0");
    expect(out.consent.versions.terms_general).toBe("v1.0");
    expect(out.consent.versions.push_notifications).toBe("v1.0");
    expect(out.consent.versions.summary_email).toBe("v1.0");
  });
});
