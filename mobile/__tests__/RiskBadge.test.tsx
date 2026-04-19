/**
 * First render test in the mobile suite.
 *
 * Constraints (both necessary to explain the shape of this test):
 *
 *  - `react-test-renderer` was deprecated in React 19 and returns
 *    `null` from `toJSON()` for components that use Fragment-based
 *    shims — so the conventional Node-side render pipeline is out.
 *  - `@testing-library/react-native` depends on internal React
 *    Native module resolution that the `jest-expo` preset normally
 *    provides; the preset itself crashes during its own setup on
 *    Node 24.
 *
 * Workaround: the shim in `__mocks__/react-native.js` renders View /
 * Text / TouchableOpacity / … as plain React Fragments, so the
 * component tree resolves to a string tree that `react-dom/server`
 * happily flattens into static markup. That's enough for copy-level
 * assertions on pure-markup leaf components (RiskBadge,
 * EmergencyBanner, ConfidenceDots, …) — exactly what a smoke-level
 * render suite needs. Anything deeper than copy (interaction,
 * accessibility, gesture) should move back to the real RN harness
 * once the `jest-expo` compat gap is unblocked.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import RiskBadge from "../components/RiskBadge";

function renderText(element: React.ReactElement): string {
  return renderToStaticMarkup(element);
}

describe("RiskBadge", () => {
  it("renders the Turkish label for LOW", () => {
    expect(renderText(<RiskBadge level="LOW" />)).toContain("Düşük Risk");
  });

  it("renders the Turkish label for MEDIUM", () => {
    expect(renderText(<RiskBadge level="MEDIUM" />)).toContain("Orta Risk");
  });

  it("renders the Turkish label for HIGH", () => {
    expect(renderText(<RiskBadge level="HIGH" />)).toContain("Yüksek Risk");
  });

  it("falls back to LOW copy for an unknown level", () => {
    // Component rule: `riskConfig[level] || riskConfig.LOW`, so
    // garbage levels surface the LOW label instead of crashing or
    // rendering blank.
    expect(renderText(<RiskBadge level="UNKNOWN_LEVEL_XYZ" />)).toContain(
      "Düşük Risk",
    );
  });

  it("still renders at small size", () => {
    expect(renderText(<RiskBadge level="HIGH" size="sm" />)).toContain(
      "Yüksek Risk",
    );
  });
});
