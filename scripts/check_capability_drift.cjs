#!/usr/bin/env node
/**
 * Capability drift-check: backend ↔ mobile parity.
 *
 * Fails (exit 1) when `KNOWN_CAPABILITIES` in
 *   backend/app/version_gating.py
 * doesn't match `CLIENT_CAPABILITIES` in
 *   mobile/src/config/capabilities.ts
 *
 * The two registries MUST stay in lock-step: the mobile build
 * advertises what it can parse, and the backend middleware trusts
 * that list. Divergence either ships dead fields (backend generates,
 * no client reads) or breaks clients (client claims a capability the
 * backend doesn't serve).
 *
 * Run: `node scripts/check_capability_drift.cjs`
 * CI:  wired into backend-regression + dashboard-tests workflows.
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

function main() {
  const backendTokens = extractBackendCapabilities(
    readFile("backend/app/version_gating.py"),
  );
  const mobileTokens = extractMobileCapabilities(
    readFile("mobile/src/config/capabilities.ts"),
  );

  const backend = new Set(backendTokens);
  const mobile = new Set(mobileTokens);

  const backendOnly = [...backend].filter((t) => !mobile.has(t)).sort();
  const mobileOnly = [...mobile].filter((t) => !backend.has(t)).sort();

  if (backendOnly.length === 0 && mobileOnly.length === 0) {
    process.stdout.write(
      `[capability-drift] ok — ${backendTokens.length} capabilities in sync: ` +
        `${backendTokens.sort().join(", ")}\n`,
    );
    return;
  }

  let msg = "backend ↔ mobile capability drift detected:\n";
  if (backendOnly.length) {
    msg += `  backend has, mobile missing: ${backendOnly.join(", ")}\n`;
  }
  if (mobileOnly.length) {
    msg += `  mobile has, backend missing: ${mobileOnly.join(", ")}\n`;
  }
  msg +=
    "  fix: update whichever side is behind, then rerun this check.\n" +
    "  see docs/client_versioning.md for the protocol.";
  fail(msg);
}

main();
