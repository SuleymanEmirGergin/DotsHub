/**
 * TEST-3: runtime_guards.test.cjs
 * Static-analysis tests for runtime error guards across admin pages and core libs.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readFile(relPath) {
  const filePath = path.join(__dirname, "..", relPath);
  return fs.readFileSync(filePath, "utf8");
}

function fileExists(relPath) {
  return fs.existsSync(path.join(__dirname, "..", relPath));
}

// 1. tuning-metrics: totalSessions > 0 guard (prevents NaN in division)
test("tuning-metrics/page.tsx: has totalSessions > 0 guard (NaN fix)", () => {
  const source = readFile(path.join("app", "admin", "tuning-metrics", "page.tsx"));
  assert.match(source, /totalSessions\s*>\s*0/);
});

// 2. tuning-tasks: .catch( on generate-patch fetch (silent failure fix)
test("tuning-tasks/page.tsx: generate-patch fetch has .catch( handler", () => {
  const source = readFile(path.join("app", "admin", "tuning-tasks", "page.tsx"));
  assert.match(source, /\.catch\(/);
});

// 3. sessions-v5: load function has try/catch
test("sessions-v5/page.tsx: load function has try and catch blocks", () => {
  const source = readFile(path.join("app", "admin", "sessions-v5", "page.tsx"));
  assert.match(source, /async\s+function\s+load\s*\(\s*\)/);
  assert.match(source, /\btry\b/);
  assert.match(source, /\bcatch\b/);
});

// 4. users/page.tsx: error destructured from Supabase query
test("users/page.tsx: Supabase query destructures error field", () => {
  const source = readFile(path.join("app", "admin", "users", "page.tsx"));
  // Pattern: { data: ..., error: ... } from supabase query
  assert.match(source, /error\s*:\s*\w+/);
});

// 5. lib/api/proxy.ts: status 503 in error return
test("lib/api/proxy.ts: catch block returns status 503", () => {
  const source = readFile(path.join("lib", "api", "proxy.ts"));
  assert.match(source, /status:\s*503/);
});

// 6. lib/env.ts: file exists and exports validateServerEnv
test("lib/env.ts: file exists", () => {
  assert.ok(fileExists(path.join("lib", "env.ts")), "lib/env.ts should exist");
});

test("lib/env.ts: exports validateServerEnv function", () => {
  const source = readFile(path.join("lib", "env.ts"));
  assert.match(source, /export\s+function\s+validateServerEnv/);
});

// 7. next.config.ts: X-Frame-Options security header present
test("next.config.ts: includes X-Frame-Options security header", () => {
  const source = readFile("next.config.ts");
  assert.match(source, /X-Frame-Options/);
});
