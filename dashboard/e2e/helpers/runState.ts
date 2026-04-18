/**
 * Read access to the run-state file written by globalSetup.
 *
 * Staging specs use this to discover the current run id, the seeded
 * session ids/labels, and the admin email. Keeps specs free of env
 * parsing + Supabase admin imports.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import type { SeededSession } from "./testData";

export interface RunState {
  runId: string;
  adminEmail: string;
  seededSessions: SeededSession[];
  baseURL: string;
}

const RUN_STATE_FILE = join(__dirname, "..", ".run-state.json");

export function readRunState(): RunState {
  if (!existsSync(RUN_STATE_FILE)) {
    throw new Error(
      `Run state not found at ${RUN_STATE_FILE}. ` +
        "globalSetup must have run — check E2E_MODE=staging and .env.staging.",
    );
  }
  return JSON.parse(readFileSync(RUN_STATE_FILE, "utf-8")) as RunState;
}

export function findSeeded(state: RunState, label: string): SeededSession {
  const hit = state.seededSessions.find((s) => s.label === label);
  if (!hit) {
    throw new Error(`Seeded session with label=${label} not found in run state`);
  }
  return hit;
}
