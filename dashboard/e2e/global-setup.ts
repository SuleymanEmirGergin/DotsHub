/**
 * Playwright global setup — runs ONCE before all tests across all workers.
 *
 * Responsibilities (only active when E2E_MODE=staging):
 *   1. Stamp a run id into process.env so tests + teardown agree.
 *   2. Provision the test admin (auth user + admin_users row).
 *   3. Sweep leftover rows from crashed previous runs.
 *   4. Seed a known set of triage_sessions for sessions.spec.
 *   5. Persist the seeded ids to disk so specs can read them.
 *
 * When E2E_MODE !== "staging", this is a no-op — localhost smoke tests
 * don't touch Supabase.
 */
import { writeFileSync } from "node:fs";
import { join } from "node:path";

import type { FullConfig } from "@playwright/test";
import { config as loadEnv } from "dotenv";

import { ensureTestAdmin } from "./helpers/auth";
import { initRunId } from "./helpers/runId";
import { supabaseAdmin } from "./helpers/supabaseAdmin";
import { seedSessions, sweepStaleRows, type SeededSession } from "./helpers/testData";

loadEnv({ path: join(__dirname, "..", ".env.staging") });

const RUN_STATE_FILE = join(__dirname, ".run-state.json");

export interface RunState {
  runId: string;
  adminEmail: string;
  seededSessions: SeededSession[];
  baseURL: string;
}

async function globalSetup(_config: FullConfig): Promise<void> {
  if (process.env.E2E_MODE !== "staging") {
    return;
  }

  const runId = initRunId();
  const adminEmail = process.env.STAGING_TEST_ADMIN_EMAIL ?? "e2e-admin@example.test";
  const baseURL = process.env.PLAYWRIGHT_BASE_URL;
  if (!baseURL) {
    throw new Error(
      "E2E_MODE=staging requires PLAYWRIGHT_BASE_URL (deployed dashboard URL).",
    );
  }

  const sb = supabaseAdmin();

  // Stale-row sweep — only touches e2e_test=true rows > 60 min old.
  const swept = await sweepStaleRows(sb, 60);
  if (swept > 0) {
    // eslint-disable-next-line no-console
    console.log(`[e2e setup] swept ${swept} stale rows from prior runs`);
  }

  // Provision admin idempotently.
  await ensureTestAdmin(sb, adminEmail, "admin");

  // Seed a deterministic set of sessions for list/filter tests.
  //
  // `recommended_specialty_tr` carries a `E2E-<runId>-...` tag so assertions
  // on the list page can find OUR rows without colliding with pre-existing
  // staging data — the list page renders specialty but not input_text, so
  // uniqueness has to live in a rendered column.
  const tag = (label: string) => `E2E-${runId}-${label}`;
  const seeded = await seedSessions(sb, runId, [
    { label: "list-first", confidence_0_1: 0.82, recommended_specialty_tr: tag("Kardiyoloji") },
    { label: "list-second", confidence_0_1: 0.41, recommended_specialty_tr: tag("Dahiliye") },
    { label: "feedback-up", confidence_0_1: 0.7, feedback: "up", recommended_specialty_tr: tag("FeedbackUp") },
    { label: "feedback-down", confidence_0_1: 0.3, feedback: "down", recommended_specialty_tr: tag("FeedbackDown") },
    {
      label: "emergency-case",
      envelope_type: "EMERGENCY",
      recommended_specialty_tr: "Acil Tıp",
      confidence_0_1: 0.95,
    },
  ]);

  const state: RunState = {
    runId,
    adminEmail,
    seededSessions: seeded,
    baseURL,
  };
  writeFileSync(RUN_STATE_FILE, JSON.stringify(state, null, 2), "utf-8");

  // eslint-disable-next-line no-console
  console.log(`[e2e setup] run_id=${runId}, seeded=${seeded.length}, admin=${adminEmail}`);
}

export default globalSetup;
