/**
 * Admin feedback E2E — localhost smoke.
 *
 * Unauthenticated path ends at the login screen. We assert the page
 * renders without a 500, the known filter query params don't crash
 * the middleware, and the optional ?rating=down URL shape (the most
 * common triage filter) parses cleanly.
 *
 * Deeper behaviour (ack button flow, specialty distribution card,
 * confusion matrix) is covered by the staging suite against a real
 * Supabase read path.
 */

import { test, expect } from "@playwright/test";

test.describe("Admin feedback — localhost smoke", () => {
  test("base route renders (login or feedback table)", async ({ page }) => {
    await page.goto("/admin/feedback");

    const heading = page.getByRole("heading", {
      name: /admin login|feedback|geri bildirim/i,
    });
    await expect(heading.first()).toBeVisible({ timeout: 8000 });
  });

  test("rating=down filter is accepted", async ({ page }) => {
    const res = await page.goto("/admin/feedback?rating=down");
    expect(res?.status() ?? 0).toBeLessThan(500);
  });

  test("rating=up filter is accepted", async ({ page }) => {
    const res = await page.goto("/admin/feedback?rating=up");
    expect(res?.status() ?? 0).toBeLessThan(500);
  });

  test("malformed filter (unknown rating) still renders", async ({ page }) => {
    // The server-side query builder should tolerate values it doesn't
    // know about (the filter defaults to "all" rather than erroring).
    // Regression-guard: somebody adds a strict enum + forgets the
    // fall-through.
    const res = await page.goto("/admin/feedback?rating=banana");
    expect(res?.status() ?? 0).toBeLessThan(500);
  });
});
