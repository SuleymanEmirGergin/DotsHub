/**
 * Client capability registry.
 *
 * Tokens this mobile build advertises via the `X-Client-Capabilities`
 * HTTP header. Each token tells the backend "I can parse this new
 * response shape"; the backend strips any field whose capability the
 * client didn't advertise. See docs/client_versioning.md for the
 * protocol.
 *
 * ─── Not the same as feature flags ──────────────────────────────────
 * `useVersionGate` + `GET /v1/config/features` handles runtime
 * behavioural flags (what the server wants the client to DO). This
 * file handles wire-shape negotiation (what response FIELDS the
 * client can parse). Both layers coexist — one says "what to show",
 * the other says "what we can read". See
 * `docs/client_versioning.md` → "Mobile side" + "Related: runtime
 * feature flags".
 *
 * ─── Advertising decision (2026-04-19 audit) ───────────────────────
 * Both current tokens verified safe to advertise for this build:
 *   - curated_meta: all nine gated top_conditions fields are optional
 *     in `src/state/types.ts::TopCondition` and conditionally rendered
 *     in `src/screens/ResultScreen.tsx` (EN→TR fallback, array length
 *     checks, accessibility disabled when nothing to expand). Missing
 *     fields collapse to zero output, never crash.
 *   - emergency_specialty: `EmergencyPayload` doesn't type the gated
 *     `recommended_specialty` field and no render path reads it —
 *     advertising is a no-op for the UI but keeps us forward-compatible
 *     for the day we DO render it in EmergencyScreen.
 *
 * ─── SYNC REQUIRED ──────────────────────────────────────────────────
 * Must stay identical to `KNOWN_CAPABILITIES` in
 *   backend/app/version_gating.py
 * `scripts/check_capability_drift.cjs` enforces parity in CI.
 *
 * ─── Adding a new capability ────────────────────────────────────────
 *   1. Define the `CAP_*` constant + add to the array below.
 *   2. Mirror in backend/app/version_gating.py (token + filter logic).
 *   3. Update docs/client_versioning.md registry table.
 *   4. Verify every rendering path for the gated field tolerates its
 *      absence (optional in types, conditional in JSX). If not,
 *      DON'T add to the array until the UI is defensive — otherwise
 *      old clients advertising this capability will crash when the
 *      backend starts emitting the field.
 *   5. Ship backend first — middleware is additive, so old clients
 *      keep working; new clients pick up the field once they upgrade.
 */

export const CAP_CURATED_META = "curated_meta" as const;
export const CAP_EMERGENCY_SPECIALTY = "emergency_specialty" as const;
// Transport-mode advertisement: this build can parse SSE events from
// /v1/triage/stream (thinking → envelope → done). Currently gates no
// payload field, but is registered so future stream-only fields can
// hide behind it. Safe to advertise: this build's chat layer reads
// `/v1/triage/stream` via fetch + ReadableStream and falls back to
// `/v1/triage/turn` if the server returns a non-SSE response.
export const CAP_STREAMING_ENVELOPE = "streaming_envelope" as const;

export type CapabilityToken =
  | typeof CAP_CURATED_META
  | typeof CAP_EMERGENCY_SPECIALTY
  | typeof CAP_STREAMING_ENVELOPE;

/** Canonical ordered list — used for header serialisation + iteration. */
export const CLIENT_CAPABILITIES: readonly CapabilityToken[] = [
  CAP_CURATED_META,
  CAP_EMERGENCY_SPECIALTY,
  CAP_STREAMING_ENVELOPE,
] as const;

export const CLIENT_CAPABILITIES_SET: ReadonlySet<CapabilityToken> = new Set(
  CLIENT_CAPABILITIES,
);

// ─── Test override ──────────────────────────────────────────────────
//
// Tests import `__testing` and push a custom set to simulate old clients.
// Kept as a separate namespace so accidental production use is loud.

let overrideCapabilities: ReadonlySet<CapabilityToken> | null = null;

function activeCapabilities(): ReadonlySet<CapabilityToken> {
  return overrideCapabilities ?? CLIENT_CAPABILITIES_SET;
}

/**
 * Serialise the active capability set into the header value.
 * Deterministic order (follows `CLIENT_CAPABILITIES` declaration order).
 */
export function getCapabilitiesHeader(): string {
  const active = activeCapabilities();
  return CLIENT_CAPABILITIES.filter((c) => active.has(c)).join(",");
}

export const __testing = {
  /** Replace the active set. Pass `null` to reset to defaults. */
  setCapabilities(caps: ReadonlySet<CapabilityToken> | null): void {
    overrideCapabilities = caps;
  },
  reset(): void {
    overrideCapabilities = null;
  },
};
