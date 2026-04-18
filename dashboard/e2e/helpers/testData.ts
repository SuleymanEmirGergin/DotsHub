/**
 * Seeding + cleanup for staging e2e runs.
 *
 * Every row we create carries `meta.e2e_test_run_id = RUN_ID`. Cleanup
 * deletes by that key. FK cascade on `triage_sessions.id` handles
 * `triage_events` and `triage_feedback` automatically (see
 * backend/sql/20260210_supabase_triage_schema.sql).
 *
 * A second, broader cleanup path ("stale-row sweep") removes any row
 * whose input_text starts with the `[E2E-` marker but whose run id is
 * older than a threshold. This recovers leaked rows if a previous run
 * crashed before teardown.
 */
import type { SupabaseClient } from "@supabase/supabase-js";

import { E2E_META_KEY, inputTextPrefix } from "./runId";

export interface TestSessionFixture {
  /** Suffix appended to input_text for readability — not a primary key. */
  label: string;
  locale?: string;
  envelope_type?: "QUESTION" | "RESULT" | "EMERGENCY" | "ERROR";
  recommended_specialty_id?: string;
  recommended_specialty_tr?: string;
  confidence_0_1?: number;
  confidence_label_tr?: string;
  feedback?: "up" | "down";
}

export interface SeededSession {
  /** UUID from DB (primary key, session_id). */
  id: string;
  label: string;
  feedback: "up" | "down" | null;
}

export async function seedSessions(
  sb: SupabaseClient,
  runId: string,
  fixtures: TestSessionFixture[],
): Promise<SeededSession[]> {
  const prefix = inputTextPrefix(runId);
  const rows = fixtures.map((f) => ({
    locale: f.locale ?? "tr-TR",
    input_text: `${prefix}${f.label}`,
    envelope_type: f.envelope_type ?? "RESULT",
    recommended_specialty_id: f.recommended_specialty_id ?? "internal_gi",
    recommended_specialty_tr: f.recommended_specialty_tr ?? "Dahiliye",
    confidence_0_1: f.confidence_0_1 ?? 0.65,
    confidence_label_tr: f.confidence_label_tr ?? "Yüksek",
    turn_index: 0,
    top_conditions: [
      { label_tr: "Test condition", probability_0_1: 0.6 },
    ],
    meta: { [E2E_META_KEY]: runId, e2e_test: true },
  }));

  const { data: inserted, error } = await sb
    .from("triage_sessions")
    .insert(rows)
    .select("id, input_text");

  if (error) {
    throw new Error(`seedSessions failed: ${error.message}`);
  }

  const seeded: SeededSession[] = (inserted ?? []).map((row, i) => ({
    id: row.id,
    label: fixtures[i].label,
    feedback: fixtures[i].feedback ?? null,
  }));

  const feedbackRows = seeded
    .filter((s) => s.feedback !== null)
    .map((s) => ({ session_id: s.id, rating: s.feedback as "up" | "down" }));

  if (feedbackRows.length) {
    const { error: fErr } = await sb.from("triage_feedback").insert(feedbackRows);
    if (fErr) {
      throw new Error(`seed feedback failed: ${fErr.message}`);
    }
  }

  return seeded;
}

/** Delete only the rows this run created. */
export async function cleanupRun(sb: SupabaseClient, runId: string): Promise<number> {
  // Supabase JS path: .filter("meta->>key", "eq", value)
  const { data, error } = await sb
    .from("triage_sessions")
    .delete()
    .filter(`meta->>${E2E_META_KEY}`, "eq", runId)
    .select("id");
  if (error) {
    throw new Error(`cleanupRun failed: ${error.message}`);
  }
  return (data ?? []).length;
}

/**
 * Broader sweep — removes any e2e-marked row older than `olderThanMinutes`.
 * Safety net for runs that crashed before teardown. Won't touch fresh runs.
 */
export async function sweepStaleRows(
  sb: SupabaseClient,
  olderThanMinutes = 60,
): Promise<number> {
  const cutoff = new Date(Date.now() - olderThanMinutes * 60_000).toISOString();
  const { data, error } = await sb
    .from("triage_sessions")
    .delete()
    .filter("meta->>e2e_test", "eq", "true")
    .lt("created_at", cutoff)
    .select("id");
  if (error) {
    // Non-fatal — log only, don't fail setup.
    // eslint-disable-next-line no-console
    console.warn(`sweepStaleRows soft-failed: ${error.message}`);
    return 0;
  }
  return (data ?? []).length;
}
