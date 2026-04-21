// Mobile i18n contract check.
//
// All five locales (tr/en/de/ru/ar) must share the same dotted-key
// set so `getText(locale, key)` never runtime-returns `undefined`
// on a missing translation. This script fails the build when any
// locale drifts from the reference set (tr.json — Turkish is the
// primary language the app ships in, and net-new keys always land
// there first).
//
// Why a contract test instead of trusting reviewers:
//   - i18n drift is the #1 bug class in multi-locale mobile apps.
//     A key added in tr.json + forgotten in de.json surfaces as an
//     empty string or the raw key name on a German user's screen —
//     we had two incidents before we hardened this on the dashboard
//     (see dashboard/scripts/check_deployments_i18n_contract.cjs).
//   - TypeScript can't catch it because the keys are strings
//     indexed off a Record<string, string>.
//   - Jest tests only exercise the current locale; a smoke test
//     can't feasibly run every screen across every locale.
//
// Extra checks (also fail on mismatch):
//   - {placeholder} interpolations — if tr.json has "{count}" for a
//     key, every locale MUST also have "{count}" (order doesn't
//     matter, presence does). Missing placeholders silently drop
//     dynamic content on the translated side.
//
// Warnings (non-fatal, printed once):
//   - Empty-string translations — key exists but value is "". This
//     flags deliberately-unset strings that the reviewer should
//     fill in. Not fatal because "empty on purpose" is sometimes
//     valid (e.g., a decorative separator).

const fs = require("node:fs");
const path = require("node:path");

const I18N_DIR = path.join(__dirname, "..", "i18n");
const LOCALES = ["tr", "en", "de", "ru", "ar"];
const REFERENCE_LOCALE = "tr";

function loadLocale(locale) {
  const filePath = path.join(I18N_DIR, `${locale}.json`);
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw);
}

// Flatten {a: {b: "x", c: "y"}} → [{"a.b":"x"}, {"a.c":"y"}].
// Returns a Map<dottedKey, value>. Arrays are treated as leaves
// (no i18n file uses arrays for structured content today).
function flatten(obj, prefix = "", out = new Map()) {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    if (prefix) out.set(prefix, obj);
    return out;
  }
  for (const key of Object.keys(obj)) {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    flatten(obj[key], nextPrefix, out);
  }
  return out;
}

// Pulls out every `{token}` placeholder from a string. Order-
// independent — we compare sets, not lists, because reviewers
// sometimes reorder in translation ("Hello {name}, you have
// {count}" vs "Sie haben {count} — {name}" is still valid as long
// as both placeholders are present).
function extractPlaceholders(value) {
  if (typeof value !== "string") return new Set();
  const matches = value.match(/\{[a-zA-Z_][a-zA-Z0-9_]*\}/g) || [];
  return new Set(matches);
}

function compareKeySets(refMap, locale, otherMap) {
  const refKeys = new Set(refMap.keys());
  const otherKeys = new Set(otherMap.keys());
  const missing = [...refKeys].filter((k) => !otherKeys.has(k)).sort();
  const extra = [...otherKeys].filter((k) => !refKeys.has(k)).sort();
  return { missing, extra };
}

function comparePlaceholders(refMap, locale, otherMap) {
  const mismatches = [];
  for (const [key, refValue] of refMap.entries()) {
    if (!otherMap.has(key)) continue; // missing-key case caught separately
    const refPh = extractPlaceholders(refValue);
    const otherPh = extractPlaceholders(otherMap.get(key));
    if (refPh.size === 0 && otherPh.size === 0) continue;
    const missingInOther = [...refPh].filter((p) => !otherPh.has(p));
    const extraInOther = [...otherPh].filter((p) => !refPh.has(p));
    if (missingInOther.length > 0 || extraInOther.length > 0) {
      mismatches.push({
        key,
        refPlaceholders: [...refPh],
        otherPlaceholders: [...otherPh],
        missing: missingInOther,
        extra: extraInOther,
      });
    }
  }
  return mismatches;
}

function findEmptyStrings(map) {
  const empties = [];
  for (const [key, value] of map.entries()) {
    if (typeof value === "string" && value.trim() === "") {
      empties.push(key);
    }
  }
  return empties.sort();
}

function main() {
  const locales = {};
  for (const locale of LOCALES) {
    locales[locale] = flatten(loadLocale(locale));
  }
  const refMap = locales[REFERENCE_LOCALE];

  const problems = [];
  const warnings = [];

  for (const locale of LOCALES) {
    if (locale === REFERENCE_LOCALE) {
      // Reference locale is checked only for empty-string warnings;
      // key-set + placeholder are compared against itself so would
      // be trivially clean.
      const empties = findEmptyStrings(refMap);
      if (empties.length > 0) {
        warnings.push(
          `${locale}: ${empties.length} empty-string translation(s):\n    - ${empties.join("\n    - ")}`,
        );
      }
      continue;
    }
    const otherMap = locales[locale];
    const { missing, extra } = compareKeySets(refMap, locale, otherMap);
    if (missing.length > 0) {
      problems.push(
        `${locale}: ${missing.length} missing key(s) (present in ${REFERENCE_LOCALE}.json, absent here):\n    - ${missing.join("\n    - ")}`,
      );
    }
    if (extra.length > 0) {
      problems.push(
        `${locale}: ${extra.length} extra key(s) (here but not in ${REFERENCE_LOCALE}.json):\n    - ${extra.join("\n    - ")}`,
      );
    }
    const phMismatches = comparePlaceholders(refMap, locale, otherMap);
    if (phMismatches.length > 0) {
      const lines = phMismatches
        .slice(0, 20)
        .map((m) =>
          `    - ${m.key}: ${REFERENCE_LOCALE}=[${m.refPlaceholders.join(",")}] vs ${locale}=[${m.otherPlaceholders.join(",")}]`,
        );
      const overflow =
        phMismatches.length > 20
          ? `\n    …and ${phMismatches.length - 20} more`
          : "";
      problems.push(
        `${locale}: ${phMismatches.length} placeholder mismatch(es):\n${lines.join("\n")}${overflow}`,
      );
    }
    const empties = findEmptyStrings(otherMap);
    if (empties.length > 0) {
      warnings.push(
        `${locale}: ${empties.length} empty-string translation(s):\n    - ${empties.join("\n    - ")}`,
      );
    }
  }

  if (warnings.length > 0) {
    process.stdout.write(
      `warnings (non-fatal):\n  - ${warnings.join("\n  - ")}\n\n`,
    );
  }

  if (problems.length > 0) {
    process.stderr.write(
      `mobile_i18n_contract_check: FAIL\n\n  - ${problems.join("\n  - ")}\n`,
    );
    process.exit(1);
  }

  const totalKeys = refMap.size;
  process.stdout.write(
    `mobile_i18n_contract_check: PASS (${LOCALES.length} locales × ${totalKeys} keys)\n`,
  );
}

main();
