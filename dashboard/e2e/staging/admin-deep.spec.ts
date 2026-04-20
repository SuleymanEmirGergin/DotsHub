/**
 * Deeper admin surface tests — session detail PDF export + analytics
 * daily summary panel.
 *
 * These pages exist BEYOND the baseline /admin/sessions list that
 * `sessions.spec.ts` covers. They rely on:
 *   - globalSetup having seeded at least one session we can open
 *   - backend reachable at NEXT_PUBLIC_API_BASE for the analytics
 *     panel's /api/admin/daily-summary fetch
 *
 * Both tests sign in fresh with the magic-link flow (same helper as
 * sessions.spec.ts).
 */
import { expect, test } from "@playwright/test";

import { generateMagicLink } from "../helpers/auth";
import { findSeeded, readRunState } from "../helpers/runState";
import { supabaseAdmin } from "../helpers/supabaseAdmin";

async function signInAsAdmin(page: import("@playwright/test").Page): Promise<void> {
  const state = readRunState();
  const sb = supabaseAdmin();
  const link = await generateMagicLink(
    sb,
    state.adminEmail,
    `${state.baseURL}/auth/callback`,
  );
  await page.goto(link);
  await page.waitForLoadState("networkidle", { timeout: 15_000 });
  if (!/\/admin\/sessions/.test(page.url())) {
    throw new Error(
      `signInAsAdmin landed on ${page.url()} instead of /admin/sessions`,
    );
  }
}

test.describe("/admin/sessions/[id] — session detail", () => {
  test("session detail renders specialty + PDF export link is present", async ({
    page,
  }) => {
    await signInAsAdmin(page);

    const state = readRunState();
    // Pick any seeded session — the first RESULT-typed one is
    // always present in the globalSetup fixtures.
    const seeded = findSeeded(state, "list-first");
    await page.goto(`/admin/sessions/${seeded.id}`);

    // Header text + specialty card presence proves the page loaded
    // (not a login redirect).
    await expect(page.getByText("Session Detail")).toBeVisible();
    await expect(
      page.getByText(`E2E-${state.runId}-`, { exact: false }).first(),
    ).toBeVisible();

    // PDF export link — assertion is on the `href` so we don't
    // depend on the exact label text (could be TR or EN). The link
    // target MUST include the session id so the proxy route hits
    // the right backend endpoint.
    const pdfLink = page.locator(
      `a[href="/api/admin/session/${seeded.id}/export-pdf"]`,
    );
    await expect(pdfLink).toBeVisible();
    // `download` attribute opts the browser into save-as dialog
    // rather than inline navigation.
    await expect(pdfLink).toHaveAttribute("download", "");
  });

  test("session detail → PDF link returns application/pdf", async ({
    page,
  }) => {
    await signInAsAdmin(page);

    const state = readRunState();
    const seeded = findSeeded(state, "list-first");

    // Fetch the PDF URL directly from the already-authed page
    // context so the session cookies are attached. If the backend
    // returns anything other than application/pdf we fail loudly.
    const response = await page.request.get(
      `/api/admin/session/${seeded.id}/export-pdf`,
    );
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/pdf");

    const body = await response.body();
    // PDF magic bytes: %PDF
    expect(body.slice(0, 4).toString()).toBe("%PDF");
    // Sanity on size — real PDFs are >1KB even for small sessions.
    // Avoids false-positives on 4-byte "%PDF" fakes.
    expect(body.length).toBeGreaterThan(1000);
  });
});

test.describe("/admin/analytics — daily summary panel", () => {
  test("analytics page loads + daily-summary cards render", async ({ page }) => {
    await signInAsAdmin(page);
    await page.goto("/admin/analytics");

    // The page auto-fetches /api/admin/daily-summary?days=7 in a
    // client component. Even if there's 0 data on staging, the
    // card titles are rendered immediately (recharts renders an
    // empty-state message rather than the chart itself).
    await expect(
      page.getByText(/G(ü|u)nl(ü|u)k triyaj say(ı|i)s(ı|i)/i),
    ).toBeVisible({ timeout: 15_000 });

    // Urgency distribution card
    await expect(
      page.getByText(/Aciliyet da(ğ|g)(ı|i)l(ı|i)m(ı|i)/i),
    ).toBeVisible();

    // Top specialties card
    await expect(
      page.getByText(/En (ç|c)ok (ö|o)nerilen bran(ş|s)lar/i),
    ).toBeVisible();
  });
});
