/**
 * Per-run test identifier.
 *
 * globalSetup stamps `E2E_RUN_ID` into process.env so every helper and
 * globalTeardown see the same value. Tests that run without globalSetup
 * (e.g. a single file invoked with `--grep`) fall back to a fresh
 * random id — safe because cleanup is idempotent.
 */
const stamp = (): string =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

export function initRunId(): string {
  if (!process.env.E2E_RUN_ID) {
    process.env.E2E_RUN_ID = stamp();
  }
  return process.env.E2E_RUN_ID;
}

export function currentRunId(): string {
  return process.env.E2E_RUN_ID ?? initRunId();
}

/** Marker written into `triage_sessions.meta` — cleanup key. */
export const E2E_META_KEY = "e2e_test_run_id";

/** Prefix for input_text so test rows are visually obvious in the UI. */
export function inputTextPrefix(runId: string): string {
  return `[E2E-${runId}] `;
}
