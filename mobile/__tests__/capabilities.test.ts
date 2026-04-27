/**
 * Unit tests for the client capability registry.
 *
 * Exercises:
 *   - default serialisation (all tokens, declaration order)
 *   - test-override path (injecting an old-client subset)
 *   - reset semantics (override cleared between tests)
 *   - drift between `CLIENT_CAPABILITIES` array and Set stay in lock-step
 */
import {
  CAP_CURATED_META,
  CAP_EMERGENCY_SPECIALTY,
  CAP_STREAMING_ENVELOPE,
  CLIENT_CAPABILITIES,
  CLIENT_CAPABILITIES_SET,
  __testing,
  getCapabilitiesHeader,
} from "../src/config/capabilities";

afterEach(() => {
  __testing.reset();
});

describe("capability registry", () => {
  it("default header lists every known capability in declaration order", () => {
    expect(getCapabilitiesHeader()).toBe(
      `${CAP_CURATED_META},${CAP_EMERGENCY_SPECIALTY},${CAP_STREAMING_ENVELOPE}`,
    );
  });

  it("array and set stay in sync", () => {
    expect(CLIENT_CAPABILITIES.length).toBe(CLIENT_CAPABILITIES_SET.size);
    for (const cap of CLIENT_CAPABILITIES) {
      expect(CLIENT_CAPABILITIES_SET.has(cap)).toBe(true);
    }
  });

  it("test override narrows the advertised set (simulating old client)", () => {
    __testing.setCapabilities(new Set([CAP_EMERGENCY_SPECIALTY]));
    expect(getCapabilitiesHeader()).toBe(CAP_EMERGENCY_SPECIALTY);
  });

  it("test override to empty set advertises nothing (minimal baseline)", () => {
    __testing.setCapabilities(new Set());
    expect(getCapabilitiesHeader()).toBe("");
  });

  it("reset restores the production default", () => {
    __testing.setCapabilities(new Set());
    expect(getCapabilitiesHeader()).toBe("");

    __testing.reset();
    expect(getCapabilitiesHeader()).toBe(
      `${CAP_CURATED_META},${CAP_EMERGENCY_SPECIALTY},${CAP_STREAMING_ENVELOPE}`,
    );
  });

  it("setCapabilities(null) equals reset", () => {
    __testing.setCapabilities(new Set());
    __testing.setCapabilities(null);
    expect(getCapabilitiesHeader()).toBe(
      `${CAP_CURATED_META},${CAP_EMERGENCY_SPECIALTY},${CAP_STREAMING_ENVELOPE}`,
    );
  });

  it("serialisation order follows CLIENT_CAPABILITIES, not insertion order of override", () => {
    // Even if the override set reports items in a different iteration
    // order, the header uses the canonical array order. Override
    // includes only 2 of the 3 known capabilities — the header must
    // reflect that subset (in canonical order).
    __testing.setCapabilities(
      new Set([CAP_EMERGENCY_SPECIALTY, CAP_CURATED_META]),
    );
    expect(getCapabilitiesHeader()).toBe(
      `${CAP_CURATED_META},${CAP_EMERGENCY_SPECIALTY}`,
    );
  });
});
