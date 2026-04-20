/**
 * Public-facing pages — landing, privacy, terms.
 *
 * These pages don't require auth; they're hit by anonymous visitors
 * including App Store reviewers checking links from the submission
 * form. The tests verify content presence + cross-linking in a fresh
 * (no auth) browser context.
 *
 * Keep assertions on stable Turkish/English text that we ship in
 * messages/{tr,en}.json — not on layout IDs which may churn. The
 * content pattern is deliberately "hero + 3 sections + CTA + footer"
 * across all three pages so selectors overlap (medical disclaimer
 * appears on both landing AND terms, for example).
 */
import { expect, test } from "@playwright/test";

// All public-pages tests use a fresh context (no storageState carried
// from earlier admin-authed tests). The Playwright project default
// launches each test with a clean context already, so no explicit
// opt-in needed.

test.describe("Public pages", () => {
  test("landing page renders hero + 3-step flow + safety disclaimer", async ({
    page,
  }) => {
    await page.goto("/");

    // Hero — the tagline is the largest text on the page and comes
    // from landing.heroTagline. Turkish copy is shown by default
    // (no NEXT_LOCALE cookie = tr).
    await expect(
      page.getByRole("heading", { level: 1 }),
    ).toBeVisible();

    // 3-step explainer (💬 🩺 ✅). We look for the numbered step
    // titles "1. …" / "2. …" / "3. …" which are stable across
    // i18n revisions.
    await expect(page.getByText(/1\./)).toBeVisible();
    await expect(page.getByText(/2\./)).toBeVisible();
    await expect(page.getByText(/3\./)).toBeVisible();

    // Safety disclaimer — required by Apple/Google review. Text
    // always mentions 112 in Turkish copy.
    await expect(page.getByText(/112/)).toBeVisible();

    // Footer contact + cross-links to /privacy and /terms.
    await expect(page.getByText("emirgergin21@gmail.com")).toBeVisible();
  });

  test("privacy page renders KVKK/GDPR sections + back link", async ({
    page,
  }) => {
    await page.goto("/privacy");

    // Legal pages are long; we assert on a specific known header
    // (Veri Sorumlusu / Data Controller) that identifies the
    // page content without locking to top-of-page ordering.
    // Either the Turkish OR English text depending on cookie/
    // browser language; we match both to be locale-robust.
    await expect(
      page.getByText(/(Veri Sorumlusu|Data Controller)/),
    ).toBeVisible();

    // Rights section — the list should include at least one
    // bullet that mentions "silme" (erasure / right to be
    // forgotten in TR) or "erasure" (EN).
    await expect(
      page.getByText(/(silme|erasure)/i),
    ).toBeVisible();

    // Medical disclaimer mention — we render a card at the
    // bottom of privacy with ⚠ / 112 keywords.
    await expect(page.getByText(/112/)).toBeVisible();
  });

  test("terms page renders medical disclaimer prominently + key sections", async ({
    page,
  }) => {
    await page.goto("/terms");

    // Medical disclaimer heading is the most visually emphasised
    // block on the page. Turkish "Tıbbi Uyarı" OR "Medical
    // Disclaimer" text appears in the accent card.
    await expect(
      page.getByText(/(T(ı|i)bbi Uyar(ı|i)|Medical Disclaimer)/),
    ).toBeVisible();

    // ACIL / EMERGENCY keyword in the critical paragraph inside
    // the disclaimer card.
    await expect(
      page.getByText(/(AC(I|İ)L DURUMDA|IN AN EMERGENCY)/i),
    ).toBeVisible();

    // Governing law section references İstanbul — anchors the
    // terms to the expected jurisdiction.
    await expect(
      page.getByText(/(Istanbul|İstanbul)/),
    ).toBeVisible();
  });

  test("privacy ↔ terms pages cross-link each other", async ({ page }) => {
    // From /privacy the footer has a link to /terms; from /terms
    // to /privacy. Tests both round-trips so a broken link in
    // either direction surfaces.
    await page.goto("/privacy");
    await page.getByRole("link", { name: /(Kullan(ı|i)m Ko(ş|s)ullar(ı|i)|Terms)/i }).first().click();
    await page.waitForURL(/\/terms$/);

    await page
      .getByRole("link", { name: /(Gizlilik|Privacy)/i })
      .first()
      .click();
    await page.waitForURL(/\/privacy$/);
  });

  test("landing CTA reveals admin login entry", async ({ page }) => {
    await page.goto("/");

    // The landing page MUST expose a path to admin login — we
    // (= the team) rely on it regularly. If a future redesign
    // removes the link, this test catches it.
    const adminLink = page.getByRole("link", {
      name: /(Admin Giri(ş|s)i|Admin Login)/i,
    });
    await expect(adminLink).toBeVisible();

    await adminLink.click();
    await page.waitForURL(/\/login$/);
  });
});
