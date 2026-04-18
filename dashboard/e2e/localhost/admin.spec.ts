import { test, expect } from "@playwright/test";

test.describe("Dashboard admin", () => {
  test("visiting /admin/sessions shows login or sessions list", async ({ page }) => {
    await page.goto("/admin/sessions");
    // Either we see login (Admin Login / email input) or sessions list (Sessions / table)
    const hasLogin = await page.getByRole("heading", { name: /admin login/i }).isVisible().catch(() => false);
    const hasSessions = await page.getByRole("heading", { name: /sessions/i }).isVisible().catch(() => false);
    expect(hasLogin || hasSessions).toBe(true);
  });

  test("login page has email input and send button", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByPlaceholder(/email|@/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /magic link|send/i })).toBeVisible();
  });

  test("visiting /admin/status shows status or login", async ({ page }) => {
    await page.goto("/admin/status");
    const hasStatus = await page.getByRole("heading", { name: /system status|sistem durumu/i }).isVisible().catch(() => false);
    const hasLogin = await page.getByRole("heading", { name: /admin login/i }).isVisible().catch(() => false);
    expect(hasStatus || hasLogin).toBe(true);
  });

  test("status page when loaded shows either login or at least one service card", async ({ page }) => {
    await page.goto("/admin/status");
    const hasLogin = await page.getByRole("heading", { name: /admin login/i }).isVisible().catch(() => false);
    if (hasLogin) {
      expect(true).toBe(true);
      return;
    }
    // When logged in: at least one status card (Backend, Supabase, Admin stats) should be visible
    const hasService = await page.getByText(/backend|supabase|admin|api|oturum|bağlantı|connection/i).first().isVisible().catch(() => false);
    expect(hasService).toBe(true);
  });
});
