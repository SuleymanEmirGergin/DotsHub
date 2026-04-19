#!/usr/bin/env node
/**
 * Capability drift-check: backend ↔ mobile ↔ docs parity.
 *
 * Fails (exit 1) when the token set in any of:
 *   - `KNOWN_CAPABILITIES` in backend/app/version_gating.py
 *   - `CLIENT_CAPABILITIES` in mobile/src/config/capabilities.ts
 *   - registry table in docs/client_versioning.md
 * disagrees with the other two.
 *
 * All three MUST stay in lock-step:
 *   - backend is the source-of-truth for what gets filtered.
 *   - mobile advertises what it can parse.
 *   - the doc is where engineers look when adding a new token, so
 *     it has to list every supported token or the checklist lies.
 *
 * Run: `node scripts/check_capability_drift.cjs`
 * CI:  `.github/workflows/capability-drift.yml`.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..");

function fail(msg) {
  process.stderr.write(`[capability-drift] ${msg}\n`);
  process.exit(1);
}

function readFile(rel) {
  const full = path.join(REPO_ROOT, rel);
  try {
    return fs.readFileSync(full, "utf8");
  } catch (err) {
    fail(`cannot read ${rel}: ${err.message}`);
  }
}

/**
 * Parse backend Python module for the KNOWN_CAPABILITIES literal.
 * Matches the frozenset declaration:
 *
 *   KNOWN_CAPABILITIES: FrozenSet[str] = frozenset({
 *       CAP_CURATED_META,
 *       CAP_EMERGENCY_SPECIALTY,
 *   })
 *
 * And resolves each `CAP_*` name to its string literal defined above.
 */
function extractBackendCapabilities(source) {
  const constants = {};
  const constRe = /^([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]+)"/gm;
  let m;
  while ((m = constRe.exec(source))) {
    if (m[1].startsWith("CAP_")) {
      constants[m[1]] = m[2];
    }
  }

  const frozensetRe = /KNOWN_CAPABILITIES[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)/;
  const block = frozensetRe.exec(source);
  if (!block) {
    fail(
      "backend/app/version_gating.py: could not locate KNOWN_CAPABILITIES frozenset literal",
    );
  }
  const names = block[1]
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  const tokens = [];
  for (const name of names) {
    if (!(name in constants)) {
      fail(
        `backend: KNOWN_CAPABILITIES references ${name} but no "${name} = \"...\"" constant was found`,
      );
    }
    tokens.push(constants[name]);
  }
  return tokens;
}

/**
 * Parse mobile TS module for CLIENT_CAPABILITIES + CAP_* constants.
 * Matches:
 *
 *   export const CAP_CURATED_META = "curated_meta" as const;
 *   export const CLIENT_CAPABILITIES: readonly CapabilityToken[] = [
 *     CAP_CURATED_META,
 *     CAP_EMERGENCY_SPECIALTY,
 *   ] as const;
 */
function extractMobileCapabilities(source) {
  const constants = {};
  const constRe =
    /export const (CAP_[A-Z0-9_]+)\s*=\s*"([^"]+)"(?:\s*as\s+const)?/g;
  let m;
  while ((m = constRe.exec(source))) {
    constants[m[1]] = m[2];
  }

  const arrRe =
    /export const CLIENT_CAPABILITIES[^=]*=\s*\[([\s\S]*?)\]\s*as\s+const/;
  const block = arrRe.exec(source);
  if (!block) {
    fail(
      "mobile/src/config/capabilities.ts: could not locate CLIENT_CAPABILITIES array literal",
    );
  }
  const names = block[1]
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  const tokens = [];
  for (const name of names) {
    if (!(name in constants)) {
      fail(
        `mobile: CLIENT_CAPABILITIES references ${name} but no "export const ${name} = \"...\"" was found`,
      );
    }
    tokens.push(constants[name]);
  }
  return tokens;
}

/**
 * Parse the markdown "registry" table in docs/client_versioning.md.
 * The table starts with a `| Token | What it unlocks |` header; each
 * subsequent row has a first-column cell of the form `| `token` | …`.
 * We extract tokens from that first column only — anything else on
 * the page (headers, prose, the capability-vs-feature-flag table) is
 * ignored.
 */
function extractDocsCapabilities(source) {
  // Find the "Token | What it unlocks" table heading. Then consume
  // data rows until the table ends (blank line or next heading).
  const lines = source.split(/\r?\n/);
  let i = 0;
  let tableStart = -1;
  for (; i < lines.length; i++) {
    if (/^\|\s*Token\s*\|\s*What it unlocks\s*\|/.test(lines[i])) {
      tableStart = i + 2; // skip header + separator row
      break;
    }
  }
  if (tableStart < 0) {
    fail(
      "docs/client_versioning.md: could not locate the `| Token | What it unlocks |` registry table",
    );
  }
  const tokens = [];
  for (let j = tableStart; j < lines.length; j++) {
    const line = lines[j];
    if (!line.startsWith("|")) break; // table ended
    const cells = line.split("|").map((c) => c.trim());
    if (cells.length < 3) continue;
    const first = cells[1]; // e.g. "`curated_meta`"
    const m = first.match(/`([a-z_][a-z0-9_]*)`/);
    if (m) tokens.push(m[1]);
  }
  if (tokens.length === 0) {
    fail(
      "docs/client_versioning.md: registry table located but no tokens parsed — the row format changed?",
    );
  }
  return tokens;
}

function diffSets(a, b) {
  return [...a].filter((t) => !b.has(t)).sort();
}

function main() {
  const backendTokens = extractBackendCapabilities(
    readFile("backend/app/version_gating.py"),
  );
  const mobileTokens = extractMobileCapabilities(
    readFile("mobile/src/config/capabilities.ts"),
  );
  const docsTokens = extractDocsCapabilities(
    readFile("docs/client_versioning.md"),
  );

  const backend = new Set(backendTokens);
  const mobile = new Set(mobileTokens);
  const docs = new Set(docsTokens);

  const issues = [];
  const addIssue = (label, missing) => {
    if (missing.length) issues.push(`  ${label}: ${missing.join(", ")}`);
  };
  addIssue("backend has, mobile missing", diffSets(backend, mobile));
  addIssue("mobile has, backend missing", diffSets(mobile, backend));
  addIssue("backend has, docs missing", diffSets(backend, docs));
  addIssue("docs has, backend missing", diffSets(docs, backend));
  addIssue("mobile has, docs missing", diffSets(mobile, docs));
  addIssue("docs has, mobile missing", diffSets(docs, mobile));

  if (issues.length === 0) {
    process.stdout.write(
      `[capability-drift] ok — ${backendTokens.length} capabilities in sync ` +
        `(backend + mobile + docs): ${backendTokens.sort().join(", ")}\n`,
    );
    return;
  }

  fail(
    "3-way capability drift detected:\n" +
      issues.join("\n") +
      "\n  fix: update whichever side is behind, then rerun this check.\n" +
      "  see docs/client_versioning.md → 'Adding a new capability'.",
  );
}

main();
