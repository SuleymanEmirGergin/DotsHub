/**
 * TEST-2: api_routes.test.cjs
 * Static-analysis contract tests for all BFF proxy route files.
 *
 * Checks per route:
 *   1. proxyFetch imported from @/lib/api/proxy
 *   2. requireAdmin() is called
 *   3. NEXT_PUBLIC_API_BASE! non-null assertion is NOT used
 *   4. if (!base) return guard is present (env var safety)
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readRoute(relPath) {
  const filePath = path.join(__dirname, "..", relPath);
  return fs.readFileSync(filePath, "utf8");
}

const ROUTES = [
  path.join("app", "api", "admin", "overview", "route.ts"),
  path.join("app", "api", "admin", "sessions", "route.ts"),
  path.join("app", "api", "admin", "session", "[session_id]", "route.ts"),
  path.join("app", "api", "admin", "stats", "route.ts"),
  path.join("app", "api", "admin", "live", "route.ts"),
  path.join("app", "api", "admin", "lowconf", "route.ts"),
  path.join("app", "api", "admin", "riskhigh", "route.ts"),
  path.join("app", "api", "admin", "webhook-test", "route.ts"),
  path.join("app", "api", "admin", "generate-patch", "[taskId]", "route.ts"),
];

for (const route of ROUTES) {
  const label = route.replace(/\\/g, "/");

  test(`${label}: imports proxyFetch from @/lib/api/proxy`, () => {
    const source = readRoute(route);
    assert.match(source, /proxyFetch.*from\s+["']@\/lib\/api\/proxy["']/s);
  });

  test(`${label}: calls requireAdmin()`, () => {
    const source = readRoute(route);
    assert.match(source, /requireAdmin\(\)/);
  });

  test(`${label}: does NOT use NEXT_PUBLIC_API_BASE! non-null assertion`, () => {
    const source = readRoute(route);
    assert.doesNotMatch(source, /NEXT_PUBLIC_API_BASE!/);
  });

  test(`${label}: has if (!base) return guard`, () => {
    const source = readRoute(route);
    assert.match(source, /if\s*\(\s*!base\s*\)/);
  });
}
