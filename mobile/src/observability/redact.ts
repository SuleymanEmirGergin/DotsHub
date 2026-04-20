/**
 * Pure redaction utilities.
 *
 * Lives in its own module (no Expo / Sentry imports) so call sites
 * like `services/api.ts` can pull in redaction without loading the
 * whole Sentry init chain. This matters for unit tests: the RN
 * `__DEV__` global isn't defined in Node's jest environment, so any
 * test that transitively imports `expo-constants` fails to load.
 * Keeping redaction Expo-free means both environments work.
 */

/**
 * Redact obvious free-text PII inline.
 *
 * Order matters: the specific patterns (UUID, email, TCKN) run
 * before the greedy phone pattern so the digits in, e.g., a UUID's
 * last segment aren't eaten as a phone number.
 */
export function redactPII(text: string): string {
  if (typeof text !== "string" || text.length === 0) return text;
  let out = text;
  out = out.replace(
    /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi,
    "[UUID]",
  );
  out = out.replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, "[EMAIL]");
  // Turkish ID number — 11 digits, first digit 1-9.
  out = out.replace(/\b[1-9][0-9]{10}\b/g, "[TCKN]");
  // Phone numbers (TR + international common shapes). Last so it
  // doesn't clobber the patterns above.
  out = out.replace(/\+?\d[\d\s().-]{8,}\d/g, "[PHONE]");
  return out;
}

/**
 * Collapse the variable segment of session-scoped URLs to a stable
 * placeholder so aggregation in Sentry / breadcrumbs doesn't explode
 * into one transaction per session.
 */
export function redactUrlPath(url: string): string {
  if (typeof url !== "string" || url.length === 0) return url;
  return url.replace(/\/v1\/session\/[^/?#]+/g, "/v1/session/[id]");
}
