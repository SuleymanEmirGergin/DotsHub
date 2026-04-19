/**
 * DisclaimerBanner render smoke.
 *
 * The banner body is hard-coded Turkish copy that sits above the
 * triage flow. Changing the string is a product decision, so the
 * test assertions match the literal copy — any accidental edit
 * (typo, truncation, locale swap) surfaces here.
 *
 * Note: the file lives at `components/SymptomInput.tsx` for
 * historical reasons; the default export is `DisclaimerBanner`.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import DisclaimerBanner from "../components/SymptomInput";

function renderText(element: React.ReactElement): string {
  return renderToStaticMarkup(element)
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

describe("DisclaimerBanner", () => {
  it("renders the info icon", () => {
    expect(renderText(<DisclaimerBanner />)).toContain("ℹ️");
  });

  it("renders the first clause of the Turkish disclaimer copy", () => {
    expect(renderText(<DisclaimerBanner />)).toContain(
      "Bu uygulama tanı koymaz",
    );
  });

  it("renders the professional-referral clause", () => {
    expect(renderText(<DisclaimerBanner />)).toContain(
      "sağlık profesyoneline",
    );
  });
});
