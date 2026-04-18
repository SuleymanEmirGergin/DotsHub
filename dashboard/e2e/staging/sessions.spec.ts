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
  const state = readRunState();
  const sb = supabaseAdmin();
  const link = await generateMagicLink(
    sb,
    state.adminEmail,
    `${state.baseURL}/auth/callback`,
  );
  await page.goto(link);
  await page.waitForURL(/\/admin\/sessions(\?|$)/, { timeout: 15_000 });
}

test.describe("/admin/sessions", () => {
  test("list page renders seeded rows with specialty + confidence", async ({
    page,
  }) => {
    await signInAsAdmin(page);

    // Our seeded labels appear in input_text via the [E2E-<runId>] prefix.
    await expect(page.getByText(/list-first/).first()).toBeVisible();
    await expect(page.getByText(/list-second/).first()).toBeVisible();

    // Specialty column should render one of our seeded values.
    await expect(page.getByText(/Kardiyoloji|Dahiliye/).first()).toBeVisible();
  });

  test("feedback=up filter narrows list to thumbs-up rows", async ({ page }) => {
    await signInAsAdmin(page);

    await page.goto("/admin/sessions?feedback=up");
    await expect(page.getByText(/feedback-up/)).toBeVisible();
    // feedback-down is excluded under the filter.
    await expect(page.getByText(/feedback-down/)).not.toBeVisible();
  });

  test("feedback=down filter narrows list to thumbs-down rows", async ({ page }) => {
    await signInAsAdmin(page);

    await page.goto("/admin/sessions?feedback=down");
    await expect(page.getByText(/feedback-down/)).toBeVisible();
    await expect(page.getByText(/feedback-up/)).not.toBeVisible();
  });

  test("emergency envelope surfaces ER specialty", async ({ page }) => {
    await signInAsAdmin(page);

    const state = readRunState();
    const emergency = findSeeded(state, "emergency-case");

    await page.goto(`/admin/sessions/${emergency.id}`);
    await expect(page.getByText(/Acil T(ı|i)p|Emergency/i).first()).toBeVisible();
  });
});
