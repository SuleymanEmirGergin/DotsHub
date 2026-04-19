/**
 * ResultCard render smoke.
 *
 * Covers:
 *   - label + percentage (`probability * 100`, rounded) both appear
 *   - percentage formatting uses the Turkish `%NN` prefix
 *   - supporting evidence bullets are rendered verbatim
 *   - empty supporting list doesn't emit the evidence block
 *
 * Follows the same `react-dom/server` + RN-shim strategy as
 * RiskBadge.test.tsx; see `mobile/__mocks__/react-native.js` for
 * background.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import ResultCard from "../components/ResultCard";

function renderText(element: React.ReactElement): string {
  return renderToStaticMarkup(element);
}

describe("ResultCard", () => {
  it("renders the label and rounded percentage", () => {
    const out = renderText(
      <ResultCard label="Peptik ülser" probability={0.714} supporting={[]} />,
    );
    expect(out).toContain("Peptik ülser");
    // 0.714 → round(71.4) = 71 — Turkish format is `%NN`.
    expect(out).toContain("%71");
  });

  it("renders every supporting evidence bullet", () => {
    const out = renderText(
      <ResultCard
        label="Akut koroner sendrom şüphesi"
        probability={0.82}
        supporting={[
          "göğüs ağrısı",
          "sol kola yayılım",
          "terleme + bulantı",
        ]}
      />,
    );
    expect(out).toContain("göğüs ağrısı");
    expect(out).toContain("sol kola yayılım");
    expect(out).toContain("terleme + bulantı");
  });

  it("rounds probability 0 correctly", () => {
    const out = renderText(
      <ResultCard label="X" probability={0} supporting={[]} />,
    );
    expect(out).toContain("%0");
  });

  it("rounds probability 1 to 100", () => {
    const out = renderText(
      <ResultCard label="Y" probability={1} supporting={[]} />,
    );
    expect(out).toContain("%100");
  });

  it("skips the evidence block when supporting is empty", () => {
    // We only emit supporting items when `supporting.length > 0` —
    // an empty list should not emit any stray `•` bullet characters.
    const out = renderText(
      <ResultCard label="Z" probability={0.5} supporting={[]} />,
    );
    expect(out).not.toContain("•");
  });
});
