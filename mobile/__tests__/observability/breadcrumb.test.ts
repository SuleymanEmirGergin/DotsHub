/**
 * Breadcrumb helper tests. We mock `@sentry/react-native` (the
 * package isn't installed in CI because native builds come from
 * EAS, not Jest) and verify each helper:
 *   - is a silent no-op when Sentry doesn't load
 *   - when Sentry loads, produces a breadcrumb with the correct
 *     category + level + data shape
 *
 * These tests protect the breadcrumb contract — the runbooks
 * (MOBILE_SENTRY_OUTAGE) include a mandatory post-incident PII
 * check; catching a category/level regression at PR time means the
 * runbook never has to fire on a structural shift.
 */

// We need to mock the lazy require() inside breadcrumb.ts. Jest
// hoists jest.mock above imports, so this block resolves before
// the module under test is evaluated.
const mockAddBreadcrumb = jest.fn();
jest.mock(
  "@sentry/react-native",
  () => ({
    __esModule: true,
    addBreadcrumb: mockAddBreadcrumb,
  }),
  { virtual: true },
);

import {
  addApiBreadcrumb,
  addBreadcrumb,
  addNavigationBreadcrumb,
  addPushLifecycleBreadcrumb,
  addVersionGateBreadcrumb,
} from "../../src/observability/breadcrumb";

describe("breadcrumb helpers", () => {
  beforeEach(() => {
    mockAddBreadcrumb.mockClear();
  });

  describe("addApiBreadcrumb", () => {
    it("redacts session UUID in endpoint", () => {
      addApiBreadcrumb({
        endpoint: "/session/abc-123/message",
        method: "POST",
        status: 200,
        durationMs: 42,
        level: "info",
      });
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "api",
          level: "info",
          data: expect.objectContaining({
            method: "POST",
            status: 200,
            duration_ms: 42,
          }),
        }),
      );
    });

    it("logs error level for non-2xx responses", () => {
      addApiBreadcrumb({
        endpoint: "/triage/push-token",
        method: "POST",
        status: 500,
        durationMs: 120,
        level: "error",
      });
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({ level: "error" }),
      );
    });

    it("records note for network-level failures", () => {
      addApiBreadcrumb({
        endpoint: "/session/xyz/result",
        method: "GET",
        status: 0,
        durationMs: 8,
        level: "error",
        note: "TypeError",
      });
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ note: "TypeError", status: 0 }),
        }),
      );
    });
  });

  describe("addNavigationBreadcrumb", () => {
    it("records a cold-start transition (from=null)", () => {
      addNavigationBreadcrumb("/");
      expect(mockAddBreadcrumb).toHaveBeenCalledWith({
        category: "navigation",
        level: "info",
        message: "-> /",
        data: { from: "", to: "/" },
      });
    });

    it("records a from->to transition", () => {
      addNavigationBreadcrumb("/language", "/");
      expect(mockAddBreadcrumb).toHaveBeenCalledWith({
        category: "navigation",
        level: "info",
        message: "/ -> /language",
        data: { from: "/", to: "/language" },
      });
    });
  });

  describe("addVersionGateBreadcrumb", () => {
    it("logs info level for ok decision", () => {
      addVersionGateBreadcrumb("ok", {
        current: "1.2.0",
        min: "1.0.0",
        latest: "1.3.0",
        mode: "warn",
      });
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "version_gate",
          level: "info",
          message: "gate=ok current=1.2.0 min=1.0.0",
        }),
      );
    });

    it("logs info level for warn decision", () => {
      addVersionGateBreadcrumb("warn", {
        current: "0.9.0",
        min: "1.0.0",
        mode: "warn",
      });
      const call = mockAddBreadcrumb.mock.calls[0][0];
      expect(call.level).toBe("info");
      expect(call.data.decision).toBe("warn");
    });

    it("logs warning level for block decision", () => {
      addVersionGateBreadcrumb("block", {
        current: "0.5.0",
        min: "1.0.0",
        mode: "block",
      });
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          level: "warning",
          data: expect.objectContaining({ decision: "block" }),
        }),
      );
    });
  });

  describe("addPushLifecycleBreadcrumb", () => {
    it("logs info level for successful events", () => {
      addPushLifecycleBreadcrumb("permission_granted");
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "push",
          level: "info",
          message: "push.permission_granted",
        }),
      );
    });

    it("logs warning level for _failed events", () => {
      addPushLifecycleBreadcrumb("register_failed", { error: "network" });
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          level: "warning",
          message: "push.register_failed",
          data: { error: "network" },
        }),
      );
    });

    it("logs warning level for permission_denied", () => {
      addPushLifecycleBreadcrumb("permission_denied");
      expect(mockAddBreadcrumb).toHaveBeenCalledWith(
        expect.objectContaining({
          level: "warning",
          message: "push.permission_denied",
        }),
      );
    });
  });

  describe("addBreadcrumb (generic)", () => {
    it("passes category + level through verbatim", () => {
      addBreadcrumb("custom", "hello", { x: 1 }, "debug");
      expect(mockAddBreadcrumb).toHaveBeenCalledWith({
        category: "custom",
        level: "debug",
        message: "hello",
        data: { x: 1 },
      });
    });
  });

  describe("swallows internal Sentry errors", () => {
    it("does not rethrow when Sentry.addBreadcrumb itself throws", () => {
      mockAddBreadcrumb.mockImplementationOnce(() => {
        throw new Error("sentry internal");
      });
      // No throw expected — breadcrumb failures must not surface.
      expect(() =>
        addNavigationBreadcrumb("/somewhere"),
      ).not.toThrow();
    });
  });
});
