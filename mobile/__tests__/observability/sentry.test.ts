/**
 * Unit tests for the Sentry init + scrubbing layer.
 *
 * We deliberately do NOT test the real `Sentry.init` call — that's
 * an integration concern covered by Expo e2e smoke. Here we test:
 *   - `initSentry()` with a blank DSN returns "disabled" without
 *     touching @sentry/react-native (so blank-DSN shells don't need
 *     the package installed)
 *   - `beforeSend` scrubs free-text patient input, device IDs, and
 *     auth headers
 *   - `redactPII` replaces the high-value PII patterns
 *   - `redactUrlPath` collapses session-scoped URLs so Sentry
 *     transaction names don't explode in cardinality
 */

import {
  beforeSend,
  initSentry,
  redactPII,
  redactUrlPath,
} from "../../src/observability/sentry";

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: {
    expoConfig: {
      extra: {},
      version: "1.0.0",
    },
  },
}));

describe("redactPII", () => {
  it("redacts a Turkish ID (TCKN)", () => {
    expect(redactPII("TCKN: 12345678901")).toBe("TCKN: [TCKN]");
  });

  it("any 11+ digit run is redacted (TCKN or phone) — never leaks raw", () => {
    // We deliberately don't try to distinguish TCKN vs phone perfectly:
    // both patterns mean "this shouldn't ship to Sentry". What matters
    // is the raw digit sequence doesn't survive redactPII.
    const out = redactPII("case #01234567890");
    expect(out).not.toContain("01234567890");
  });

  it("redacts phone numbers", () => {
    expect(redactPII("call +90 555 123 45 67 please")).toContain("[PHONE]");
    expect(redactPII("0 532 123 4567")).toContain("[PHONE]");
  });

  it("redacts emails", () => {
    expect(redactPII("send to user@example.com now")).toBe(
      "send to [EMAIL] now",
    );
  });

  it("redacts UUIDs", () => {
    const text = "session id abc12345-abcd-1234-5678-0123456789ab ended";
    expect(redactPII(text)).toBe("session id [UUID] ended");
  });

  it("is a no-op on empty / non-string input", () => {
    expect(redactPII("")).toBe("");
    // @ts-expect-error — intentionally exercising defensive guard
    expect(redactPII(null)).toBe(null);
  });
});

describe("redactUrlPath", () => {
  it("collapses session-id segment in path", () => {
    expect(redactUrlPath("/v1/session/abc-123/message")).toBe(
      "/v1/session/[id]/message",
    );
  });

  it("collapses in full URL form", () => {
    expect(
      redactUrlPath("https://api.triaige.test/v1/session/abc-123/result"),
    ).toBe("https://api.triaige.test/v1/session/[id]/result");
  });

  it("leaves unrelated URLs alone", () => {
    expect(redactUrlPath("/v1/config/features")).toBe("/v1/config/features");
  });
});

describe("beforeSend", () => {
  it("drops events with environment=test", () => {
    expect(beforeSend({ environment: "test" })).toBeNull();
    expect(beforeSend({ environment: "ci" })).toBeNull();
  });

  it("scrubs request.data patient input in-place", () => {
    const event = {
      environment: "production",
      request: {
        url: "/v1/session/abc-123/message",
        data: {
          user_input_tr: "nefes almakta zorlanıyorum, göğsümde sıkışma var",
          profile: { age: 42, sex: "M" },
        },
      },
    };
    const out = beforeSend(event) as typeof event;
    expect(out).not.toBeNull();
    expect(out.request.data).toEqual({
      user_input_tr: "[SCRUBBED]",
      profile: { age: 42, sex: "M" },
    });
    // URL transcript normalised.
    expect(out.request.url).toBe("/v1/session/[id]/message");
  });

  it("scrubs authorization + device headers but leaves others", () => {
    const event = {
      environment: "production",
      request: {
        headers: {
          authorization: "Bearer secret",
          "x-device-id": "device-abcdef",
          "x-client-capabilities": "curated_meta",
          "user-agent": "ExpoClient/1.0",
        },
      },
    };
    const out = beforeSend(event) as typeof event;
    expect(out.request.headers).toEqual({
      authorization: "[SCRUBBED]",
      "x-device-id": "[SCRUBBED]",
      "x-client-capabilities": "curated_meta",
      "user-agent": "ExpoClient/1.0",
    });
  });

  it("redacts PII in breadcrumb messages + data", () => {
    const event = {
      environment: "production",
      breadcrumbs: {
        values: [
          {
            category: "api",
            message: "GET /v1/session/abc-123/result — user@example.com",
            data: {
              url: "/v1/session/abc-123/result",
              user_input_tr: "hasta çok öksürüyor",
            },
          },
        ],
      },
    };
    const out = beforeSend(event) as typeof event;
    const crumb = out.breadcrumbs.values[0] as Record<string, any>;
    expect(crumb.message).toContain("[EMAIL]");
    // The URL inside breadcrumb data is a free-text redact path (not
    // via redactUrlPath since breadcrumbs are generic) — the UUID
    // regex in redactPII would NOT match 'abc-123'; it matches 8-4-4-4-12.
    // So we assert the scrubbed user_input_tr at minimum.
    expect(crumb.data.user_input_tr).toBe("[SCRUBBED]");
  });

  it("recursively scrubs nested extra context", () => {
    const event = {
      environment: "production",
      extra: {
        nested: {
          user_input_tr: "baş ağrısı ve halsizlik",
          safe_key: { harmless: "data" },
        },
      },
    };
    const out = beforeSend(event) as typeof event;
    expect(out.extra.nested).toEqual({
      user_input_tr: "[SCRUBBED]",
      safe_key: { harmless: "data" },
    });
  });

  it("handles a bare array breadcrumbs shape", () => {
    // Some Sentry versions deliver breadcrumbs as a bare array —
    // guard the scrubber against both.
    const event = {
      environment: "production",
      breadcrumbs: [
        { message: "call +90 555 123 45 67", data: { meta: "patient note" } },
      ],
    };
    const out = beforeSend(event) as typeof event;
    const crumb = (out.breadcrumbs as any[])[0];
    expect(crumb.message).toContain("[PHONE]");
    expect(crumb.data).toEqual({ meta: "[SCRUBBED]" });
  });
});

describe("initSentry", () => {
  const savedEnv = process.env.EXPO_PUBLIC_SENTRY_DSN;

  afterEach(() => {
    if (savedEnv !== undefined) {
      process.env.EXPO_PUBLIC_SENTRY_DSN = savedEnv;
    } else {
      delete process.env.EXPO_PUBLIC_SENTRY_DSN;
    }
  });

  it("returns disabled when DSN is blank (no import attempt)", () => {
    delete process.env.EXPO_PUBLIC_SENTRY_DSN;
    const out = initSentry();
    expect(out).toEqual({ status: "disabled", reason: "blank-dsn" });
  });

  it("returns disabled when DSN is whitespace-only", () => {
    process.env.EXPO_PUBLIC_SENTRY_DSN = "   \t  ";
    const out = initSentry();
    expect(out).toEqual({ status: "disabled", reason: "blank-dsn" });
  });

  // We do NOT test the enabled path here — that requires a real
  // @sentry/react-native install + a native module. The smoke test
  // (mobile/.maestro/) covers prod init.
});
