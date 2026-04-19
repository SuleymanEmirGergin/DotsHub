/**
 * /admin/sessions — list, filter, detail against live staging.
 *
 * Each test authenticates fresh via admin-generated magic link (no
 * storageState reuse) because sharing auth between serial tests hides
 * cookie-TTL bugs we want e2e to catch.
 *
 * Test data comes from globalSetup's seed — we look up rows by their
 * known `label` to avoid brittle "first row" assertions.
 */
import { expect, test } from "@playwright/test";

import { generateMagicLink } from "../helpers/auth";
import { findSeeded, readRunState } from "../helpers/runState";
import { supabaseAdmin } from "../helpers/supabaseAdmin";

async function signInAsAdmin(page: import("@playwright/test").Page): Promise<void> {
  // Capture browser-side errors + console so staging-only failures
  // (JS throws from `createBrowserClient`, setSession errors, cookie-
  // domain warnings) surface in the assertion message. Otherwise the
  // failure looks identical to "no session cookies" regardless of the
  // actual cause.
  const consoleLines: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (msg) => {
    const type = msg.type();
    if (type === "error" || type === "warning") {
      consoleLines.push(`[${type}] ${msg.text()}`);
    }
  });
  page.on("pageerror", (err) => {
    pageErrors.push(`${err.name}: ${err.message}`);
  });

  const state = readRunState();
  const sb = supabaseAdmin();
  const link = await generateMagicLink(
    sb,
    state.adminEmail,
    `${state.baseURL}/auth/callback`,
  );
  await page.goto(link);
  // Give the callback page time to setSession → router.replace,
  // AND the server component to run requireAdmin (which may redirect).
  await page.waitForLoadState("networkidle", { timeout: 15_000 });

  const finalUrl = page.url();
  if (!/\/admin\/sessions/.test(finalUrl)) {
    const cookies = await page.context().cookies();
    const allCookieNames = cookies.map((c) => c.name).sort();
    const sbCookies = cookies
      .filter((c) => c.name.includes("sb-") || c.name.includes("supabase"))
      .map((c) => `${c.name}=${c.value.slice(0, 20)}…`);

    throw new Error(
      [
        `signInAsAdmin landed on ${finalUrl}, expected /admin/sessions.`,
        `All cookie names: [${allCookieNames.join(", ") || "NONE"}]`,
        `Supabase cookies: [${sbCookies.join(", ") || "NONE"}]`,
        `Page errors: ${pageErrors.length ? pageErrors.join(" | ") : "(none)"}`,
        `Console errors/warnings (last 10): ${
          consoleLines.slice(-10).join(" | ") || "(none)"
        }`,
      ].join("\n"),
    );
  }
}

test.describe("/admin/sessions", () => {
  test("list page renders seeded rows with specialty + confidence", async ({
    page,
  }) => {
    await signInAsAdmin(page);

    // The list page renders `recommended_specialty_tr`; globalSetup seeds
    // `E2E-<runId>-...` into that column so assertions can match our rows
    // without colliding with pre-existing staging data.
    const state = readRunState();
    await expect(page.getByText(`E2E-${state.runId}-Kardiyoloji`)).toBeVisible();
    await expect(page.getByText(`E2E-${state.runId}-Dahiliye`)).toBeVisible();
  });

  test("feedback=up filter narrows list to thumbs-up rows", async ({ page }) => {
    await signInAsAdmin(page);
    const state = readRunState();

    await page.goto("/admin/sessions?feedback=up");
    await expect(page.getByText(`E2E-${state.runId}-FeedbackUp`)).toBeVisible();
    // feedback-down's specialty tag must NOT appear under this filter.
    await expect(page.getByText(`E2E-${state.runId}-FeedbackDown`)).not.toBeVisible();
  });

  test("feedback=down filter narrows list to thumbs-down rows", async ({ page }) => {
    await signInAsAdmin(page);
    const state = readRunState();

    await page.goto("/admin/sessions?feedback=down");
    await expect(page.getByText(`E2E-${state.runId}-FeedbackDown`)).toBeVisible();
    await expect(page.getByText(`E2E-${state.runId}-FeedbackUp`)).not.toBeVisible();
  });

  test("emergency envelope surfaces ER specialty", async ({ page }) => {
    await signInAsAdmin(page);

    const state = readRunState();
    const emergency = findSeeded(state, "emergency-case");

    await page.goto(`/admin/sessions/${emergency.id}`);
    await expect(page.getByText(/Acil T(ı|i)p|Emergency/i).first()).toBeVisible();
  });
});
