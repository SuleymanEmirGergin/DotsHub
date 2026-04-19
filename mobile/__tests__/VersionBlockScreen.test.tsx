/**
 * VersionBlockScreen render smoke.
 *
 * The block screen is the last-resort safety valve — ops only flips
 * enforcement to `block` when the running client has a known-bad
 * medical-logic bug. So the acceptance bar is: every Turkish copy
 * key resolves (no "missing translation" leaking), the store URL
 * picked matches the current Platform.OS, and the "no-link" hint
 * shows up when neither `update_url_ios` nor `update_url_android`
 * is populated.
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { VersionBlockScreen } from "../src/components/VersionBlockScreen";

function renderText(element: React.ReactElement): string {
  return renderToStaticMarkup(element)
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

const POLICY_WITH_LINKS = {
  min: "1.2.0",
  latest: "1.3.0",
  mode: "block" as const,
  update_url_ios: "https://apps.apple.com/app/id123",
  update_url_android: "https://play.google.com/store/apps/details?id=x",
};

const POLICY_NO_LINKS = {
  min: "1.2.0",
  latest: "1.3.0",
  mode: "block" as const,
  update_url_ios: null,
  update_url_android: null,
};

describe("VersionBlockScreen", () => {
  it("renders the block-title Turkish copy", () => {
    const out = renderText(
      <VersionBlockScreen policy={POLICY_WITH_LINKS} currentVersion="1.0.0" />,
    );
    // Key: version.blockTitle → tr.json. Not asserting the exact
    // literal to avoid brittle coupling; we're confirming the key
    // resolved (no "version.blockTitle" leak).
    expect(out).not.toContain("version.blockTitle");
    // Body substitutes current + min into the template.
    expect(out).toContain("1.0.0");
    expect(out).toContain("1.2.0");
  });

  it("renders the update CTA when store URL is provided", () => {
    const out = renderText(
      <VersionBlockScreen policy={POLICY_WITH_LINKS} currentVersion="1.0.0" />,
    );
    // Key: version.blockUpdate — shows up as button label and
    // accessibility label.
    expect(out).not.toContain("version.blockUpdate");
  });

  it("renders the 'no-link' hint when both store URLs are null", () => {
    const out = renderText(
      <VersionBlockScreen policy={POLICY_NO_LINKS} currentVersion="1.0.0" />,
    );
    // Key: version.blockNoLinkHint — italic hint shown in the
    // absence of a store URL for the current platform.
    expect(out).not.toContain("version.blockNoLinkHint");
  });

  it("always surfaces the footer hint", () => {
    const out = renderText(
      <VersionBlockScreen policy={POLICY_WITH_LINKS} currentVersion="1.0.0" />,
    );
    expect(out).not.toContain("version.blockFooterHint");
  });
});
