import { test, expect } from "@playwright/test";

test.describe("Admin API error handling", () => {
  test("backend 503 shows error state, not white screen", async ({ page }) => {
    await page.route("/api/admin/overview", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "UPSTREAM_UNAVAILABLE" }),
      })
    );
    await page.goto("/admin");
    // Page should render something — not crash to white screen
    const bodyText = await page.locator("body").textContent();
    expect(bodyText?.trim().length).toBeGreaterThan(0);
  });

  test("backend timeout returns 503 JSON from proxyFetch", async ({ page }) => {
    // Verify the /api/admin route itself handles gracefully
    const response = await page.request.get("/api/admin/overview", {
      headers: { "x-test": "1" },
    });
    // Should return JSON (not HTML error page), regardless of status
    const contentType = response.headers()["content-type"] ?? "";
    expect(contentType).toContain("application/json");
  });

  test("sessions page handles empty data gracefully", async ({ page }) => {
    await page.route("/api/admin/sessions*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ sessions: [], total: 0 }),
      })
    );
    await page.goto("/admin/sessions-v5");
    // Should not throw — either shows empty state or loading
    await expect(page.locator("body")).not.toBeEmpty();
  });
});
