const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function readComponent(relPath) {
  const filePath = path.join(__dirname, "..", relPath);
  return fs.readFileSync(filePath, "utf8");
}

test("Breadcrumb component renders items and uses Link for href", () => {
  const source = readComponent(path.join("app", "components", "Breadcrumb.tsx"));
  assert.match(source, /BreadcrumbItem|label.*href/);
  assert.match(source, /items\.map/);
  assert.match(source, /Link/);
  assert.match(source, /item\.href/);
  assert.match(source, /aria-label.*Breadcrumb/);
});
