/**
 * Playwright global teardown — deletes every row we seeded for this run.
 *
 * Uses the run_id persisted by globalSetup (on disk via .run-state.json,
 * and as process.env.E2E_RUN_ID for in-process use). Cascade FKs on
 * `triage_sessions.id` remove associated `triage_events` and
 * `triage_feedback` rows automatically.
 */
import { existsSync, readFileSync, unlinkSync } from "node:fs";
import { join } from "node:path";

import type { FullConfig } from "@playwright/test";

import { supabaseAdmin } from "./helpers/supabaseAdmin";
import { cleanupRun } from "./helpers/testData";

const RUN_STATE_FILE = join(__dirname, ".run-state.json");

async function globalTeardown(_config: FullConfig): Promise<void> {
  if (process.env.E2E_MODE !== "staging") {
    return;
  }

  let runId = process.env.E2E_RUN_ID;
  if (!runId && existsSync(RUN_STATE_FILE)) {
    try {
      const state = JSON.parse(readFileSync(RUN_STATE_FILE, "utf-8")) as { runId?: string };
      runId = state.runId;
    } catch {
      // fall through — no id, nothing to clean
    }
  }
  if (!runId) {
     
    console.warn("[e2e teardown] no run_id found; skipping cleanup");
    return;
  }

  try {
    const sb = supabaseAdmin();
    const removed = await cleanupRun(sb, runId);
     
    console.log(`[e2e teardown] removed ${removed} rows for run_id=${runId}`);
  } catch (err) {
    // Teardown failures must not mask test results — log and continue.
     
    console.error(`[e2e teardown] cleanup error: ${(err as Error).message}`);
  } finally {
    if (existsSync(RUN_STATE_FILE)) {
      try {
        unlinkSync(RUN_STATE_FILE);
      } catch {
        // ignore
      }
    }
  }
}

export default globalTeardown;
