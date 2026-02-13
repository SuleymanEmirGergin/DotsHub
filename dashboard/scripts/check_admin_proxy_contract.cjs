const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readRoute(relPath) {
  const filePath = path.join(__dirname, "..", relPath);
  return fs.readFileSync(filePath, "utf8");
}

function verifySessionProxyRoute() {
  const source = readRoute(path.join("app", "api", "admin", "session", "[session_id]", "route.ts"));
  assert.match(source, /\/admin\/sessions\/\$\{session_id\}/);
  assert.match(source, /"x-admin-key"/);
  assert.match(source, /NEXT_PUBLIC_API_BASE/);
  assert.match(source, /ADMIN_API_KEY/);
}

function verifyTuningPatchProxyRoute() {
  const source = readRoute(
    path.join("app", "api", "admin", "tuning-tasks", "[task_id]", "generate-patch", "route.ts"),
  );
  assert.match(source, /\/v1\/admin\/tuning-tasks\/\$\{task_id\}\/generate-patch/);
  assert.match(source, /"x-admin-key"/);
  assert.match(source, /NEXT_PUBLIC_API_BASE/);
  assert.match(source, /ADMIN_API_KEY/);
}

function main() {
  verifySessionProxyRoute();
  verifyTuningPatchProxyRoute();
  console.log("admin_proxy_contract_check: PASS");
}

main();
