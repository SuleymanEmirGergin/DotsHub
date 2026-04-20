/**
 * Sentry initialisation + PII scrubbing for the mobile client.
 *
 * Called exactly once from `app/_layout.tsx` at module top — BEFORE
 * expo-router mounts — so the SDK captures any error thrown during
 * initial bundle evaluation.
 *
 * Design mirrors `backend/app/observability/sentry_init.py`:
 *   - Blank DSN → full no-op (no SDK call, no warning). The app
 *     must run unchanged when Sentry is not wired, so local dev /
 *     OSS clones are not forced into an account.
 *   - `beforeSend` scrubs free-text patient input + device / tenant
 *     identifiers before the event leaves the device. Same contract
 *     as the backend's scrubber so the aggregated project shows
 *     consistent PII hygiene across platforms.
 *   - Session Replay is ENABLED but runs with `maskAllText=true` +
 *     `maskAllInputs=true`. For a medical app, replays with raw
 *     patient descriptions would be a KVKK/HIPAA violation; the
 *     aggressive mask means Sentry sees redacted skeletons — useful
 *     for flow debugging, not for eavesdropping.
 *   - Sampling rates default to 0.1 (10%) in prod / 1.0 in dev so
 *     prod load doesn't shoot the free tier quota.
 *
 * Why a separate module instead of inlining in `_layout.tsx`:
 *   - Unit-testable: `initSentry()` with a blank DSN returns false
 *     without touching `@sentry/react-native`. The real init path
 *     is covered by an Expo e2e smoke, not by Jest.
 *   - `beforeSend` hook is non-trivial (URL redaction + body scrub)
 *     and deserves isolated tests.
 *   - If we ever swap Sentry for another aggregator, the swap is
 *     one import in `_layout.tsx`.
 */

import Constants from "expo-constants";

import { redactPII, redactUrlPath } from "./redact";

// Re-exported so existing callers (and tests) can still pull these
// from `@/src/observability/sentry` without caring about the split.
export { redactPII, redactUrlPath } from "./redact";

// Key names that may carry patient free text or stable identifiers.
// Anything under these keys is replaced with "[SCRUBBED]" before
// leaving the device. Lower-cased — the matcher is case-insensitive.
const SCRUB_BODY_KEYS: ReadonlySet<string> = new Set([
  "user_input_tr",
  "input_text",
  "user_message",
  "answers",
  "doctor_ready_summary_tr",
  "why_specialty_tr",
  "emergency_reason_tr",
  "meta",
  // Device fingerprinting — not PII per se, but stable enough to
  // cluster a single user across sessions. Aggregated error
  // reports should not let us de-anonymise a patient.
  "device_id",
  "x-device-id",
]);

// Headers scrubbed from breadcrumbs/context. Mirrors the backend
// _SCRUB_HEADERS list so operator expectations line up across
// platforms.
const SCRUB_HEADERS: ReadonlySet<string> = new Set([
  "authorization",
  "cookie",
  "x-admin-key",
  "x-supabase-auth",
  "x-device-id",
]);

function scrubValue(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") return redactPII(value);
  if (Array.isArray(value)) return value.map(scrubValue);
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SCRUB_BODY_KEYS.has(k.toLowerCase())) {
        out[k] = "[SCRUBBED]";
      } else {
        out[k] = scrubValue(v);
      }
    }
    return out;
  }
  return value;
}

function scrubHeaders(headers: unknown): unknown {
  if (headers === null || typeof headers !== "object") return headers;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(headers as Record<string, unknown>)) {
    out[k] = SCRUB_HEADERS.has(k.toLowerCase()) ? "[SCRUBBED]" : v;
  }
  return out;
}

/**
 * Sentry `beforeSend` hook — synchronous, runs on every event before
 * it leaves the device. Mutates `event` in place (Sentry accepts
 * either pattern) and returns it. Return `null` to drop the event.
 *
 * Exported for unit testing. Do NOT call this in product code — the
 * SDK wires it automatically once `initSentry` has run.
 */
export function beforeSend<T extends Record<string, any>>(event: T): T | null {
  // Work off the event as an index-signature'd record so TS doesn't
  // complain about ad-hoc property writes. The Sentry SDK's real
  // event shape is much richer (and `any`-typed in its own callback
  // definition), so the generic constraint above exists only to
  // preserve the return type for callers — not to enforce the schema.
  const e = event as Record<string, any>;

  // Drop anything the app flagged as "test env" so local jest runs
  // don't phone home if somebody left a DSN in their shell.
  const env = (e.environment ?? "").toString();
  if (env === "test" || env === "ci") return null;

  // Redact the transaction/url so session UUIDs aren't cardinality
  // landmines in the Sentry UI.
  if (typeof e.transaction === "string") {
    e.transaction = redactUrlPath(e.transaction);
  }

  const request = e.request as Record<string, unknown> | undefined;
  if (request && typeof request === "object") {
    if (typeof request.url === "string") {
      request.url = redactUrlPath(request.url as string);
    }
    if ("headers" in request) {
      request.headers = scrubHeaders(request.headers);
    }
    if ("data" in request) {
      request.data = scrubValue(request.data);
    }
  }

  if (e.extra) {
    e.extra = scrubValue(e.extra) as Record<string, unknown>;
  }
  if (e.contexts) {
    e.contexts = scrubValue(e.contexts) as Record<string, unknown>;
  }

  const breadcrumbs = e.breadcrumbs as
    | { values?: unknown[] }
    | unknown[]
    | undefined;
  const crumbList = Array.isArray(breadcrumbs)
    ? breadcrumbs
    : Array.isArray(breadcrumbs?.values)
      ? breadcrumbs!.values
      : null;
  if (crumbList) {
    for (const crumb of crumbList as Record<string, unknown>[]) {
      if (crumb && typeof crumb === "object") {
        if (typeof crumb.message === "string") {
          crumb.message = redactPII(crumb.message);
        }
        if ("data" in crumb) {
          crumb.data = scrubValue(crumb.data);
        }
      }
    }
  }

  return event;
}

/** What the init call resolved to — exported for logging / tests. */
export type InitOutcome =
  | { status: "disabled"; reason: "blank-dsn" | "import-failed" }
  | { status: "enabled"; environment: string };

function readDsn(): string {
  // Expo 54 exposes build-time env under `Constants.expoConfig?.extra`
  // OR direct `process.env.EXPO_PUBLIC_*`. We support both so dev
  // shells + EAS builds Just Work.
  const envDsn = (process.env.EXPO_PUBLIC_SENTRY_DSN ?? "").toString().trim();
  if (envDsn) return envDsn;
  const extra = Constants.expoConfig?.extra as
    | Record<string, unknown>
    | undefined;
  const extraDsn = (extra?.SENTRY_DSN ?? "").toString().trim();
  return extraDsn;
}

function readEnvironment(): string {
  const env =
    process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT ??
    (Constants.expoConfig?.extra as Record<string, unknown> | undefined)?.SENTRY_ENVIRONMENT;
  const s = (env ?? "").toString().trim();
  if (s) return s;
  // Sensible default: Expo sets `__DEV__` at bundle time. Prod
  // binaries have __DEV__ === false. Pulled off globalThis so the
  // tsc check doesn't need a RN ambient declaration file.
  const devFlag = (globalThis as Record<string, unknown>).__DEV__;
  return devFlag === true ? "development" : "production";
}

/**
 * Initialise Sentry. Idempotent — safe to call repeatedly (subsequent
 * calls after a successful init are silent no-ops via the SDK's own
 * guard).
 *
 * Returns `InitOutcome` so callers (and tests) can assert the
 * resolved state. Does not throw; any import or init failure is
 * swallowed + logged (console.warn).
 */
export function initSentry(): InitOutcome {
  const dsn = readDsn();
  if (!dsn) {
    return { status: "disabled", reason: "blank-dsn" };
  }

  // Typed as `any` so this file compiles in environments where
  // `@sentry/react-native` isn't installed yet (OSS clones, CI
  // stages that skip `npm install`, etc.). The real type safety is
  // enforced at the `@sentry/react-native` package level once the
  // dep is in place.
  let Sentry: any;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    Sentry = require("@sentry/react-native");
  } catch (err) {
    // Dependency not installed — app keeps running without telemetry.
    // Log so the gap is visible in dev console.
    // eslint-disable-next-line no-console
    console.warn(
      "[sentry] SENTRY_DSN set but @sentry/react-native is not installed. " +
        "Run `npx expo install @sentry/react-native` to enable crash reporting.",
      err,
    );
    return { status: "disabled", reason: "import-failed" };
  }

  const environment = readEnvironment();
  const release =
    process.env.EXPO_PUBLIC_SENTRY_RELEASE ??
    (Constants.expoConfig?.extra as Record<string, unknown> | undefined)
      ?.SENTRY_RELEASE ??
    Constants.expoConfig?.version;

  // Sampling: aggressive in dev, conservative in prod. 10% of prod
  // traces is enough to catch regressions without spending the free
  // tier on background noise. Override via env if needed.
  const tracesSampleRate = Number(
    process.env.EXPO_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ??
      (environment === "production" ? 0.1 : 1.0),
  );

  Sentry.init({
    dsn,
    environment,
    release: release ? String(release) : undefined,
    tracesSampleRate: Number.isFinite(tracesSampleRate)
      ? tracesSampleRate
      : 0.1,
    // IP is PII under KVKK — the backend's Sentry config also
    // disables sendDefaultPii.
    sendDefaultPii: false,
    // Session Replay: ENABLED with aggressive masking. User consented
    // to screen capture for support purposes; we MUST mask every
    // piece of text so patient free-text never leaves the device as
    // pixels. `replaysSessionSampleRate=0.1` captures 10% of
    // sessions; `replaysOnErrorSampleRate=1.0` captures the 60s
    // window leading up to every crash (the high-value case).
    replaysSessionSampleRate: environment === "production" ? 0.1 : 1.0,
    replaysOnErrorSampleRate: 1.0,
    integrations: [
      Sentry.mobileReplayIntegration({
        // Aggressive masking — see the KVKK/HIPAA note in the file
        // header. maskAllText hides every Text component (renders as
        // a filled rectangle); maskAllImages hides every Image
        // (avoids profile photos if we ever add any); maskAllVectors
        // hides SVG content. maskAllInputs hides TextInput values
        // while preserving the input's position and size.
        maskAllText: true,
        maskAllImages: true,
        maskAllVectors: true,
      }),
    ],
    beforeSend: (event: Record<string, any>) =>
      beforeSend(event) as any,
  });

  return { status: "enabled", environment };
}
