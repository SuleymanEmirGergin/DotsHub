/**
 * Accessibility audits for the public dashboard pages, run in
 * both light + dark themes via axe-core.
 *
 * Why this sits alongside the Lighthouse CI job
 * ----------------------------------------------
 * Lighthouse already scores `categories:accessibility` per URL
 * (pinned to >= 0.9 in `dashboard/lighthouserc.json` at Session 13).
 * That signal is a single composite number, and it only runs against
 * the default theme — whatever the page renders after a cold page
 * load with an empty localStorage. Dark mode would stay untested.
 *
 * This spec layers three things on top of the existing gate:
 *
 *   1. Per-page axe rule results in BOTH themes. Dark mode's colour
 *      contrast comes from different CSS tokens; a regression on the
 *      dark palette wouldn't surface in the light-mode Lighthouse
 *      score at all.
 *   2. Rule-level visibility. axe's `violations` array gives us the
 *      specific failing rule, target selector, and help URL per
 *      finding — Lighthouse rolls these up into a category score.
 *      When a PR does fail the gate, the failure output points the
 *      reviewer at the exact element to fix.
 *   3. Serious/critical filtering. We gate on `impact ∈ {serious,
 *      critical}` only, matching the "blocking" bar Lighthouse uses
 *      internally. `moderate` and `minor` findings are logged as
 *      test.info() annotations so they're visible in the report
 *      without flaking PRs on taste disagreements with axe's rules.
 *
 * Dark-mode setup
 * ---------------
 * The dashboard's ThemeToggle stores `light` / `dark` in
 * localStorage and applies `.dark` + `data-theme="dark"` on
 * `<html>`. We DON'T click the toggle (sometimes the toggle isn't
 * rendered yet at page-load) — instead we seed the localStorage
 * + class directly via `page.addInitScript`. That fires BEFORE any
 * other scripts on the page, so the React tree renders dark from
 * frame 1 and the toggle reads the right initial state.
 */

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PUBLIC_URLS = ["/", "/login", "/privacy", "/terms"] as const;

// Seed localStorage + apply the `.dark` class before React mounts,
// so every element renders with the dark tokens on first paint.
// Matches the ThemeToggle contract exactly:
//   localStorage["pretriage-dashboard-theme"] = "dark"
//   document.documentElement.classList.add("dark")
//   document.documentElement.setAttribute("data-theme", "dark")
async function seedDarkTheme(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("pretriage-dashboard-theme", "dark");
    } catch {
      // Private-mode or iframe contexts can throw — we still apply
      // the class below so styling matches even without storage.
    }
    const html = document.documentElement;
    html.classList.add("dark");
    html.setAttribute("data-theme", "dark");
  });
}

// Filter down to the `serious` + `critical` impact levels, which
// match Lighthouse's blocking bar. We still attach the full list
// (including `moderate` + `minor`) as test-info annotations so
// reviewers can triage without chasing links.
type AxeViolation = Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"][number];

function partitionViolations(all: AxeViolation[]): {
  blocking: AxeViolation[];
  informational: AxeViolation[];
} {
  const blocking: AxeViolation[] = [];
  const informational: AxeViolation[] = [];
  for (const v of all) {
    if (v.impact === "serious" || v.impact === "critical") {
      blocking.push(v);
    } else {
      informational.push(v);
    }
  }
  return { blocking, informational };
}

function formatViolation(v: AxeViolation): string {
  const nodes = v.nodes
    .slice(0, 3)
    .map((n) => `    - ${n.target.join(" ")} (${n.failureSummary?.slice(0, 120) ?? "no summary"})`)
    .join("\n");
  const extra = v.nodes.length > 3 ? `\n    …and ${v.nodes.length - 3} more node(s)` : "";
  return (
    `[${v.impact ?? "?"}] ${v.id}: ${v.help}\n` +
    `  Help URL: ${v.helpUrl}\n` +
    `  Nodes:\n${nodes}${extra}`
  );
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`A11y — ${theme} theme`, () => {
    for (const url of PUBLIC_URLS) {
      test(`${url} has no serious or critical violations`, async ({ page }, testInfo) => {
        if (theme === "dark") {
          await seedDarkTheme(page);
        }
        await page.goto(url);
        // Wait for the page to stabilise — Next.js App Router
        // hydrates progressively, and axe scanning mid-hydration
        // produces false positives on elements not-yet-rendered.
        await page.waitForLoadState("networkidle");

        const results = await new AxeBuilder({ page })
          // The default rule set is WCAG 2.1 AA + best practices.
          // Best-practices is noisier (e.g. `region` rule flags
          // non-landmark content) and fires often on public
          // landing content that doesn't strictly need multiple
          // landmarks. Scope to WCAG 2.1 AA so we gate on what a
          // real screen-reader user would hit.
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();

        const { blocking, informational } = partitionViolations(results.violations);

        // Attach the informational list to the test report so
        // reviewers see moderate/minor findings even when the PR
        // passes. Attaching as a plain-text body keeps it cheap to
        // open in Playwright's HTML report.
        if (informational.length > 0) {
          await testInfo.attach("informational-violations.txt", {
            body: informational.map(formatViolation).join("\n\n"),
            contentType: "text/plain",
          });
        }

        // Assertion body: stringify the blocking findings so the
        // Playwright failure log shows WHAT broke, not just "expected
        // 0 but got N".
        const message =
          blocking.length === 0
            ? ""
            : `\n\n${blocking.length} serious/critical a11y violation(s) on ${url} (${theme} theme):\n\n` +
              blocking.map(formatViolation).join("\n\n");

        expect(blocking, message).toHaveLength(0);
      });
    }
  });
}
