/**
 * Client capability registry.
 *
 * Tokens this mobile build advertises via the `X-Client-Capabilities`
 * HTTP header. Each token tells the backend "I can parse this new
 * response shape"; the backend strips any field whose capability the
 * client didn't advertise. See docs/client_versioning.md for the
 * protocol.
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
 *   4. Ship backend first — middleware is additive, so old clients
 *      keep working; new clients pick up the field once they upgrade.
 */

export const CAP_CURATED_META = "curated_meta" as const;
export const CAP_EMERGENCY_SPECIALTY = "emergency_specialty" as const;

export type CapabilityToken =
  | typeof CAP_CURATED_META
  | typeof CAP_EMERGENCY_SPECIALTY;

/** Canonical ordered list — used for header serialisation + iteration. */
export const CLIENT_CAPABILITIES: readonly CapabilityToken[] = [
  CAP_CURATED_META,
  CAP_EMERGENCY_SPECIALTY,
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
