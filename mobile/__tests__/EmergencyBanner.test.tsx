/**
 * EmergencyBanner render smoke — same pattern as RiskBadge.test.tsx.
 *
 * We care that:
 *   - title ("ACİL DURUM UYARISI") always appears
 *   - `reason` prop is conditionally rendered
 *   - every `instructions` string shows up verbatim as a bullet
 *
 * Details on why we use `react-dom/server` + a Fragment-based RN shim
 * instead of the upstream RN testing harness live in
 * `mobile/__mocks__/react-native.js`.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import EmergencyBanner from "../components/EmergencyBanner";

// `renderToStaticMarkup` emits HTML-escaped output ('apostrophe' →
// `&#x27;`), so we decode the handful of entities we actually hit
// before running substring assertions — otherwise Turkish copy like
// "112'yi arayın" is impossible to match naturally.
function renderText(element: React.ReactElement): string {
  return renderToStaticMarkup(element)
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

describe("EmergencyBanner", () => {
  it("always shows the title", () => {
    expect(
      renderText(<EmergencyBanner instructions={["112'yi arayın"]} />),
    ).toContain("ACİL DURUM UYARISI");
  });

  it("renders every instruction string verbatim", () => {
    const out = renderText(
      <EmergencyBanner
        instructions={[
          "112'yi arayın",
          "Yakın acil servise gidin",
          "Hastayı tek başına bırakmayın",
        ]}
      />,
    );
    expect(out).toContain("112'yi arayın");
    expect(out).toContain("Yakın acil servise gidin");
    expect(out).toContain("Hastayı tek başına bırakmayın");
  });

  it("renders the reason when provided", () => {
    const out = renderText(
      <EmergencyBanner
        instructions={["112"]}
        reason="Şiddetli göğüs ağrısı + sol kola yayılım"
      />,
    );
    expect(out).toContain("Şiddetli göğüs ağrısı");
  });

  it("omits the reason block when the prop is absent", () => {
    const out = renderText(<EmergencyBanner instructions={["112"]} />);
    // Nothing else shouts "reason" into the output — just title + the
    // single bullet plus icon. If the component ever starts emitting
    // a placeholder for a missing reason, that should be a conscious
    // change and this test will flag it.
    expect(out).not.toMatch(/reason/i);
  });

  it("handles an empty instructions array without crashing", () => {
    const out = renderText(<EmergencyBanner instructions={[]} />);
    expect(out).toContain("ACİL DURUM UYARISI");
  });
});
