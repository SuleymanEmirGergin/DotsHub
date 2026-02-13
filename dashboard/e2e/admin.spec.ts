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
});
