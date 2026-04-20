/**
 * Breadcrumb bridge: converts structured API events into Sentry
 * breadcrumbs, with a graceful fallback when Sentry isn't installed
 * / initialised.
 *
 * The breadcrumb module is separate from `sentry.ts` so the call
 * sites (services/api.ts, hooks, screens) can add breadcrumbs
 * without pulling the full Sentry init into their import graph.
 * When Sentry is disabled (blank DSN), every call here is a
 * near-zero-cost no-op.
 */

import { redactUrlPath } from "./redact";

type BreadcrumbLevel = "debug" | "info" | "warning" | "error";

interface ApiBreadcrumbInput {
  endpoint: string;
  method: string;
  status: number;
  durationMs: number;
  level: BreadcrumbLevel;
  /** Short tag for non-HTTP failures, e.g. "AbortError", "TypeError". */
  note?: string;
}

/**
 * Add one `api` breadcrumb to the Sentry trail.
 *
 * - `endpoint` is collapsed via `redactUrlPath` so session UUIDs
 *   aren't cardinality landmines.
 * - Never raises: if the Sentry module is missing, exits silently.
 */
export function addApiBreadcrumb(input: ApiBreadcrumbInput): void {
  const Sentry = loadSentry();
  if (!Sentry) return;

  try {
    Sentry.addBreadcrumb({
      category: "api",
      level: input.level,
      message: `${input.method} ${redactUrlPath(input.endpoint)} → ${input.status}`,
      data: {
        endpoint: redactUrlPath(input.endpoint),
        method: input.method,
        status: input.status,
        duration_ms: input.durationMs,
        ...(input.note ? { note: input.note } : {}),
      },
    });
  } catch {
    // Swallow — breadcrumb add must never surface an error to the
    // user-facing code path. Sentry init might still be spinning up
    // or the global handler might be unwound.
  }
}

/**
 * Generic breadcrumb — for non-API events like navigation, feature
 * gate decisions, etc. Pass-through wrapper so callers don't import
 * @sentry/react-native directly.
 */
export function addBreadcrumb(
  category: string,
  message: string,
  data?: Record<string, unknown>,
  level: BreadcrumbLevel = "info",
): void {
  const Sentry = loadSentry();
  if (!Sentry) return;
  try {
    Sentry.addBreadcrumb({ category, level, message, data });
  } catch {
    // swallow — see note above
  }
}

/**
 * Navigation breadcrumb — records a route transition. Called from
 * `useNavigationBreadcrumbs` on every pathname change. Keeps the
 * Sentry breadcrumb trail in sync with what the user saw on screen.
 *
 * `from` may be null on the very first render (cold start); Sentry
 * still accepts the entry and renders it as an open arrow.
 */
export function addNavigationBreadcrumb(
  to: string,
  from: string | null = null,
): void {
  const Sentry = loadSentry();
  if (!Sentry) return;
  try {
    const message = from ? `${from} -> ${to}` : `-> ${to}`;
    Sentry.addBreadcrumb({
      category: "navigation",
      level: "info",
      message,
      data: { from: from ?? "", to },
    });
  } catch {
    // swallow
  }
}

/**
 * Version-gate decision breadcrumb — fires once per
 * `useVersionGate` resolution. Records what the gate decided and
 * the inputs that drove the decision. Without this, "the gate
 * blocked me" bug reports arrive with no trace; with it, ops can
 * see `policy.min` vs. `current` at the moment of decision.
 *
 * `decision` matches the `VersionGateState.state` discriminator:
 * "ok" / "warn" / "block". We never log "loading" — that's a UI
 * state, not a final decision.
 */
export type VersionGateDecision = "ok" | "warn" | "block";

export function addVersionGateBreadcrumb(
  decision: VersionGateDecision,
  ctx: {
    current: string;
    min?: string;
    latest?: string;
    mode?: string;
  },
): void {
  const Sentry = loadSentry();
  if (!Sentry) return;
  try {
    const level: BreadcrumbLevel =
      decision === "block" ? "warning" : "info";
    Sentry.addBreadcrumb({
      category: "version_gate",
      level,
      message: `gate=${decision} current=${ctx.current}${
        ctx.min ? ` min=${ctx.min}` : ""
      }`,
      data: {
        decision,
        current: ctx.current,
        min: ctx.min ?? "",
        latest: ctx.latest ?? "",
        mode: ctx.mode ?? "",
      },
    });
  } catch {
    // swallow
  }
}

/**
 * Push-notification lifecycle breadcrumb. The push flow has five
 * terminal states any of which can silently break delivery:
 *   - permission_granted / permission_denied
 *   - token_acquired / token_missing
 *   - registered / register_failed
 *   - unregistered / unregister_failed
 *
 * We want each terminal state in the Sentry trail so "user didn't
 * get push" bug reports can be diagnosed without a full repro.
 */
export type PushLifecycleEvent =
  | "permission_granted"
  | "permission_denied"
  | "token_acquired"
  | "token_missing"
  | "registered"
  | "register_failed"
  | "unregistered"
  | "unregister_failed";

export function addPushLifecycleBreadcrumb(
  event: PushLifecycleEvent,
  data?: Record<string, unknown>,
): void {
  const Sentry = loadSentry();
  if (!Sentry) return;
  try {
    const level: BreadcrumbLevel =
      event.endsWith("_failed") || event === "permission_denied"
        ? "warning"
        : "info";
    Sentry.addBreadcrumb({
      category: "push",
      level,
      message: `push.${event}`,
      data: data ?? {},
    });
  } catch {
    // swallow
  }
}

// Lazy, cached loader. Allocating a `require` call on every
// breadcrumb would punish fast success paths. We resolve once and
// store null if Sentry isn't available — subsequent calls short-
// circuit in O(1).
//
// Typed as `any` so this file compiles when `@sentry/react-native`
// isn't installed (e.g. in OSS clones). The API surface we use
// (`addBreadcrumb`) is stable across v5/v6/v7 of the SDK, so losing
// structural typing here is low-risk.
let cached: any | null | undefined;
function loadSentry(): any | null {
  if (cached !== undefined) return cached;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    cached = require("@sentry/react-native");
  } catch {
    cached = null;
  }
  return cached;
}
