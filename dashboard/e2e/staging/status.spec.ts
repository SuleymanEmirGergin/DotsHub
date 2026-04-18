/**
 * /admin/status health tiles — live staging check.
 *
 * Validates that the status page successfully probes the real backend
 * and real Supabase connection for the current run. We only assert on
 * presence + rough state; this is a smoke test, not a health monitor.
 */
import { expect, test } from "@playwright/test";

import { generateMagicLink } from "../helpers/auth";
import { readRunState } from "../helpers/runState";
import { supabaseAdmin } from "../helpers/supabaseAdmin";

test.describe("/admin/status", () => {
  test("shows backend + supabase service cards after admin login", async ({ page }) => {
    const state = readRunState();
    const sb = supabaseAdmin();
    const link = await generateMagicLink(
      sb,
      state.adminEmail,
      `${state.baseURL}/auth/callback`,
    );
    await page.goto(link);
    await page.waitForURL(/\/admin/, { timeout: 15_000 });

    await page.goto("/admin/status");

    // Tile labels are localised; either TR or EN acceptable.
    await expect(
      page.getByText(/backend|sistem|api|oturum|bağlant(ı|i)|connection|supabase/i).first(),
    ).toBeVisible();

    // At least one tile should display an explicit OK/FAIL/state token so
    // we know the probe actually returned something rather than a spinner.
    await expect(
      page.getByText(/ok|healthy|up|down|fail|error|hata|çalış(ı|i)yor/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });
});
