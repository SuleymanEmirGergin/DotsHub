/**
 * TEST-1: proxy_fetch.test.cjs
 * Static-analysis contract tests for lib/api/proxy.ts
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const PROXY_PATH = path.join(__dirname, "..", "lib", "api", "proxy.ts");

function readProxy() {
  return fs.readFileSync(PROXY_PATH, "utf8");
}

test("lib/api/proxy.ts file exists", () => {
  assert.ok(fs.existsSync(PROXY_PATH), `Expected file to exist: ${PROXY_PATH}`);
});

test("proxy.ts exports async function proxyFetch with correct signature", () => {
  const source = readProxy();
  assert.match(source, /export\s+async\s+function\s+proxyFetch/);
});

test("proxy.ts implements timeout via AbortController", () => {
  const source = readProxy();
  // Must use AbortController (or AbortSignal.timeout) for timeout
  assert.match(source, /AbortController|AbortSignal\.timeout/);
});

test("proxy.ts returns status 503 in the catch block", () => {
  const source = readProxy();
  assert.match(source, /status:\s*503/);
});

test("proxy.ts includes upstream_timeout error message", () => {
  const source = readProxy();
  assert.match(source, /upstream_timeout/);
});

test("proxy.ts includes upstream_unreachable error message", () => {
  const source = readProxy();
  assert.match(source, /upstream_unreachable/);
});
