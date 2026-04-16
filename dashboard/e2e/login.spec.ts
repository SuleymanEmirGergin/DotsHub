import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("shows email input and submit button", async ({ page }) => {
    await expect(page.locator("input[type=email]")).toBeVisible();
    await expect(page.locator("button[type=submit]")).toBeVisible();
  });

  test("submit button is disabled without valid email", async ({ page }) => {
    const btn = page.locator("button[type=submit]");
    await expect(btn).toBeDisabled();
  });

  test("submit button is enabled with valid email", async ({ page }) => {
    await page.fill("input[type=email]", "admin@example.com");
    await expect(page.locator("button[type=submit]")).toBeEnabled();
  });

  test("form can be submitted with Enter key", async ({ page }) => {
    await page.fill("input[type=email]", "admin@example.com");
    // Mock the Supabase auth endpoint so it doesn't actually send email
    await page.route("**/auth/v1/**", (route) =>
      route.fulfill({ status: 200, body: JSON.stringify({ user: null }) })
    );
    await page.press("input[type=email]", "Enter");
    // Should not navigate away — still on login page or shows success message
    await expect(page).toHaveURL(/login/);
  });

  test("page has proper heading", async ({ page }) => {
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });
});
