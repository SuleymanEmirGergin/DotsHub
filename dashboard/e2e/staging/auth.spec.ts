/**
 * Magic-link auth — real flow against staging Supabase.
 *
 * We use `auth.admin.generateLink({ type: "magiclink" })` (Service Role)
 * to obtain the callback URL without hitting email delivery. The link
 * contains a real, unused one-time token, so navigating to it exercises:
 *   - Supabase `/auth/v1/verify` (token → code exchange via PKCE/OTP)
 *   - our `/auth/callback` page (exchange code for session)
 *   - cookie-based session establishment
 *   - redirect to admin
 *
 * Also verifies the non-admin rejection path: a plain authed user
 * without an `admin_users` row must land on `/login?e=not_admin`.
 */
import { expect, test } from "@playwright/test";

import { ensureTestAdmin, generateMagicLink } from "../helpers/auth";
import { readRunState } from "../helpers/runState";
import { supabaseAdmin } from "../helpers/supabaseAdmin";

test.describe("magic link auth", () => {
  test("admin user can sign in via admin-generated link and reach /admin/sessions", async ({
    page,
  }) => {
    const state = readRunState();
    const sb = supabaseAdmin();

    const redirectTo = `${state.baseURL}/auth/callback`;
    const link = await generateMagicLink(sb, state.adminEmail, redirectTo);

    await page.goto(link);
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    const finalUrl = page.url();
    if (!/\/admin\/sessions/.test(finalUrl) || /\/login/.test(finalUrl)) {
      const cookies = await page.context().cookies();
      const sbCookies = cookies
        .filter((c) => c.name.includes("sb-") || c.name.includes("supabase"))
        .map((c) => c.name);
      throw new Error(
        `Magic link sign-in landed on ${finalUrl}. sb-* cookies: [${sbCookies.join(", ") || "NONE"}].`,
      );
    }

    // Sessions heading (TR or EN) — requireAdmin must have passed.
    await expect(
      page.getByRole("heading", { name: /sessions|oturumlar/i }),
    ).toBeVisible();
  });

  test("login page exposes email input + submit button", async ({ page }) => {
    const state = readRunState();
    await page.goto(`${state.baseURL}/login`);
    await expect(page.getByPlaceholder(/email|@/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /magic link|send|gönder/i }),
    ).toBeVisible();
  });

  test("non-admin authed user is redirected to /login?e=not_admin", async ({
    page,
    browser,
  }) => {
    const state = readRunState();
    const sb = supabaseAdmin();

    const nonAdminEmail = `e2e-nonadmin-${state.runId}@example.test`;

    // Create the user WITHOUT admin_users row.
    const { error } = await sb.auth.admin.createUser({
      email: nonAdminEmail,
      email_confirm: true,
      user_metadata: { e2e_test_admin: false },
    });
    if (error && !/already|exists|registered/i.test(error.message)) {
      throw error;
    }

    try {
      // Fresh context so cookies from the admin test don't leak in.
      const ctx = await browser.newContext();
      const freshPage = await ctx.newPage();

      const link = await generateMagicLink(
        sb,
        nonAdminEmail,
        `${state.baseURL}/auth/callback`,
      );
      await freshPage.goto(link);

      await freshPage.waitForURL(/\/login\?e=not_admin/, { timeout: 15_000 });
      await expect(freshPage).toHaveURL(/e=not_admin/);

      await ctx.close();
    } finally {
      // Clean up the throwaway user — teardown only handles the admin one.
      const { data: list } = await sb.auth.admin.listUsers({ page: 1, perPage: 200 });
      const found = list?.users.find(
        (u) => u.email?.toLowerCase() === nonAdminEmail.toLowerCase(),
      );
      if (found) {
        await sb.auth.admin.deleteUser(found.id);
      }
    }
  });

  test("idempotent admin provisioning — ensureTestAdmin can be called twice", async () => {
    const state = readRunState();
    const sb = supabaseAdmin();
    const a = await ensureTestAdmin(sb, state.adminEmail);
    const b = await ensureTestAdmin(sb, state.adminEmail);
    expect(a.id).toBe(b.id);
    expect(a.email.toLowerCase()).toBe(state.adminEmail.toLowerCase());
  });
});
