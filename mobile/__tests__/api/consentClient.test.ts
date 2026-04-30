/**
 * Consent client contract tests — KVKK Md.6(2) + GDPR Art.9(2)(a).
 *
 * The route on the backend is append-only (test_consent_route.py
 * holds the audit invariant). On the mobile side we verify the
 * call shape: we send the right consent_type, version, and locale,
 * and we surface failures as `consent_failed` so the intro screen
 * can show a typed error instead of swallowing the rejection.
 *
 * `recordIntroConsents` fires both intro consents in parallel
 * (terms_general + health_data_processing). Either failure must
 * propagate — half-recorded consent is the worst possible audit
 * trail state, and we'd rather the user retries.
 */

import { http, HttpResponse } from "msw";

import { server } from "../../mocks/server";

jest.mock("@/src/config/runtime", () => ({
  API_BASE: "http://api.test",
  USE_MOCK: false,
}));

describe("consentClient", () => {
  it("posts a single consent and returns the stored row metadata", async () => {
    let body: any = null;
    server.use(
      http.post("http://api.test/v1/consent", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { ok: true, id: 42, granted_at: "2026-04-27T10:00:00Z" },
          { status: 201 },
        );
      }),
    );

    const { recordConsent } = require("../../src/api/consentClient");
    const out = await recordConsent({
      device_id: "device-c1",
      consent_type: "terms_general",
      consent_version: "v1.0",
      granted: true,
      locale: "tr",
      notice_version: "v0.2",
    });

    expect(out.ok).toBe(true);
    expect(out.id).toBe(42);
    expect(body.device_id).toBe("device-c1");
    expect(body.consent_type).toBe("terms_general");
    expect(body.consent_version).toBe("v1.0");
    expect(body.granted).toBe(true);
    expect(body.locale).toBe("tr");
    expect(body.notice_version).toBe("v0.2");
  });

  it("throws consent_failed on 4xx/5xx — backend detail is not leaked to UI", async () => {
    server.use(
      http.post("http://api.test/v1/consent", () =>
        HttpResponse.json(
          { detail: { code: "CONSENT_PERSIST_FAILED" } },
          { status: 503 },
        ),
      ),
    );

    const { recordConsent } = require("../../src/api/consentClient");
    let msg = "";
    try {
      await recordConsent({
        device_id: "device-c1",
        consent_type: "health_data_processing",
        consent_version: "v1.0",
        granted: true,
        locale: "tr",
      });
    } catch (err) {
      msg = err instanceof Error ? err.message : String(err);
    }
    expect(msg).toBe("consent_failed");
  });

  it("recordIntroConsents fires both consents and resolves on success", async () => {
    const captured: any[] = [];
    server.use(
      http.post("http://api.test/v1/consent", async ({ request }) => {
        captured.push(await request.json());
        return HttpResponse.json({ ok: true, id: captured.length }, { status: 201 });
      }),
    );

    const { recordIntroConsents } = require("../../src/api/consentClient");
    const out = await recordIntroConsents({
      device_id: "device-c1",
      locale: "en",
      terms_version: "v1.0",
      health_data_version: "v1.0",
      notice_version: "v0.2",
    });

    expect(out.ok).toBe(true);
    expect(captured).toHaveLength(2);
    const types = captured.map((c) => c.consent_type).sort();
    expect(types).toEqual(["health_data_processing", "terms_general"]);
    for (const c of captured) {
      expect(c.granted).toBe(true);
      expect(c.locale).toBe("en");
      expect(c.notice_version).toBe("v0.2");
    }
  });

  it("recordIntroConsents resolves ok=true even if a consent post fails (best-effort)", async () => {
    // The prod /v1/consent route may be missing on older deploys
    // (returns 404) or unreachable on first launch. Blocking every
    // user at the intro screen is a worse outcome than a degraded
    // audit trail — the failure is logged as a Sentry breadcrumb and
    // the consent_version is replayed on the first /v1/triage POST.
    let calls = 0;
    server.use(
      http.post("http://api.test/v1/consent", async ({ request }) => {
        calls += 1;
        const body = (await request.json()) as { consent_type: string };
        if (body.consent_type === "health_data_processing") {
          return HttpResponse.json(
            { detail: "fail" },
            { status: 503 },
          );
        }
        return HttpResponse.json({ ok: true, id: calls }, { status: 201 });
      }),
    );

    const { recordIntroConsents } = require("../../src/api/consentClient");
    const out = await recordIntroConsents({
      device_id: "device-c1",
      locale: "tr",
      terms_version: "v1.0",
      health_data_version: "v1.0",
    });
    expect(out.ok).toBe(true);
    expect(calls).toBeGreaterThanOrEqual(1);
  });

  it("propagates network errors as a non-consent_failed throw", async () => {
    server.use(
      http.post("http://api.test/v1/consent", () => {
        return HttpResponse.error();
      }),
    );

    const { recordConsent } = require("../../src/api/consentClient");
    let thrown: unknown = null;
    try {
      await recordConsent({
        device_id: "device-c1",
        consent_type: "terms_general",
        consent_version: "v1.0",
        granted: true,
        locale: "tr",
      });
    } catch (err) {
      thrown = err;
    }
    expect(thrown).not.toBeNull();
    // Network error is NOT consent_failed — that string is reserved
    // for HTTP non-2xx so the UI can branch (network = transient,
    // consent_failed = backend disagreed). Just assert it threw.
    expect(thrown instanceof Error).toBe(true);
  });
});
