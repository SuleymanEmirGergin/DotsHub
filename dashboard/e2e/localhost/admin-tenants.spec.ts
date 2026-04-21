/**
 * Admin tenants E2E — localhost smoke.
 *
 * Tenants admin is a Next.js proxy over the backend's curated-catalog
 * endpoints. Localhost tests here verify:
 *   - the list + detail routes render (login or content shell)
 *   - the dynamic route segment (/admin/tenants/[id]) tolerates any
 *     string without 500 (guards against a middleware regex bug)
 *   - the catalog editor textarea + save button are keyboard-reachable
 *     when the authenticated path happens to be available
 *
 * The *authenticated* workflow — edit JSON → save → reload → see
 * round-trip — is covered in the staging suite because it requires
 * a live backend + ADMIN_API_KEY.
 */

import { test, expect } from "@playwright/test";

test.describe("Admin tenants — localhost smoke", () => {
  test("listing route renders", async ({ page }) => {
    await page.goto("/admin/tenants");

    const heading = page.getByRole("heading", {
      name: /admin login|kiracı|tenant/i,
    });
    await expect(heading.first()).toBeVisible({ timeout: 8000 });
  });

  test("detail route with a made-up tenant slug still renders", async ({ page }) => {
    // Dynamic route segment — catches middleware regex bugs. If the
    // backend is unreachable, the page gracefully shows the
    // "Yüklenemedi" fallback card, which is also fine for this smoke.
    const res = await page.goto("/admin/tenants/smoke-test-slug");
    expect(res?.status() ?? 0).toBeLessThan(500);

    const hasLogin = await page
      .getByRole("heading", { name: /admin login/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasDetail = await page
      .getByRole("heading", { name: /kiracı|tenant/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasFailure = await page
      .getByText(/yüklenemedi|failed to load/i)
      .first()
      .isVisible()
      .catch(() => false);
    expect(hasLogin || hasDetail || hasFailure).toBe(true);
  });

  test("catalog editor structure (when authenticated path renders)", async ({ page }) => {
    await page.goto("/admin/tenants/default");

    const hasLogin = await page
      .getByRole("heading", { name: /admin login/i })
      .first()
      .isVisible()
      .catch(() => false);
    if (hasLogin) {
      // On an unauthed localhost run this is the expected path; mark
      // the test as covered and exit. The staging suite exercises the
      // authed flow.
      test.info().annotations.push({
        type: "skip-reason",
        description: "unauthenticated localhost — editor not rendered",
      });
      return;
    }

    // When the auth path happens to be open (dev impersonation,
    // session cookie from a previous browser run), verify the
    // editor's core controls are reachable.
    const textarea = page.locator("textarea");
    const saveButton = page.getByRole("button", { name: /kaydet|save/i });
    await expect(textarea).toBeVisible();
    await expect(saveButton).toBeVisible();
  });
});
