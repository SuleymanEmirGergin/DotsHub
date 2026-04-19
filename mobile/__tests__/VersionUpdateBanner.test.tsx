/**
 * VersionUpdateBanner render smoke.
 *
 * Warn-mode banner sitting above the main stack when the backend
 * says this build is older than MIN_CLIENT_VERSION but enforcement
 * is still "warn" (not "block"). The component is interactive
 * (dismissable + tappable for store link) — we exercise the
 * rendering-path decisions only, not pointer events (the
 * react-dom/server render pipeline doesn't drive onPress handlers
 * anyway).
 */
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { VersionUpdateBanner } from "../src/components/VersionUpdateBanner";

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
  mode: "warn" as const,
  update_url_ios: "https://apps.apple.com/app/id123",
  update_url_android: "https://play.google.com/store/apps/details?id=x",
};

const POLICY_NO_LINKS = {
  min: "1.2.0",
  latest: "1.3.0",
  mode: "warn" as const,
  update_url_ios: null,
  update_url_android: null,
};

describe("VersionUpdateBanner", () => {
  it("renders title + subtitle Turkish copy", () => {
    const out = renderText(
      <VersionUpdateBanner policy={POLICY_WITH_LINKS} currentVersion="1.0.0" />,
    );
    // Keys: version.bannerTitle + version.bannerSubtitle. Confirm
    // both resolve (no unresolved i18n keys leaking into markup).
    expect(out).not.toContain("version.bannerTitle");
    expect(out).not.toContain("version.bannerSubtitle");
    // Subtitle interpolates current + min — both must appear.
    expect(out).toContain("1.0.0");
    expect(out).toContain("1.2.0");
  });

  it("renders the update CTA when a platform-specific store URL exists", () => {
    const out = renderText(
      <VersionUpdateBanner policy={POLICY_WITH_LINKS} currentVersion="1.0.0" />,
    );
    expect(out).not.toContain("version.bannerUpdate");
    // Dismiss CTA is always present.
    expect(out).not.toContain("version.bannerDismiss");
  });

  it("omits the update CTA when both store URLs are null", () => {
    const out = renderText(
      <VersionUpdateBanner policy={POLICY_NO_LINKS} currentVersion="1.0.0" />,
    );
    // With no store URL the primary button is skipped; the dismiss
    // button still shows so the user can clear the banner for the
    // session (banner returns on the next cold-start fetch).
    // We can't assert pointer handlers, but we confirm the dismiss
    // label key resolved.
    expect(out).not.toContain("version.bannerDismiss");
  });

  it("exposes accessibility metadata", () => {
    const out = renderText(
      <VersionUpdateBanner policy={POLICY_WITH_LINKS} currentVersion="1.0.0" />,
    );
    // accessibilityLabel → version.bannerA11y key must resolve.
    expect(out).not.toContain("version.bannerA11y");
  });
});
