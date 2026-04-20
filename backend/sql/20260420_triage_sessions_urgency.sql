-- Add `urgency` column to triage_sessions.
--
-- Why this migration exists
-- -------------------------
-- The 2026-02-10 initial schema (`20260210_supabase_triage_schema.sql`)
-- did NOT include a `urgency` column, but backend code writes this
-- field on every RESULT envelope:
--
--   app/api/routes/message.py:204
--       urgency=state.routing_output.urgency if state else "ROUTINE"
--   app/api/routes/session.py:268
--   app/agents/orchestrator.py:739,817,857
--
-- On a fresh Supabase instance the first triage turn fails with:
--
--   PGRST204: Could not find the 'urgency' column of 'triage_sessions'
--             in the schema cache
--
-- Triaige prod (Fly.io) hits this every time. This migration closes
-- the gap without requiring any backend change.
--
-- Idempotent (IF NOT EXISTS) so re-running on already-migrated
-- databases is a no-op.

ALTER TABLE public.triage_sessions
    ADD COLUMN IF NOT EXISTS urgency text DEFAULT 'ROUTINE';

COMMENT ON COLUMN public.triage_sessions.urgency IS
    'Triage urgency verdict. One of: ER_NOW, SAME_DAY, WITHIN_3_DAYS, ROUTINE. '
    'Default ROUTINE applied to legacy rows where the column did not exist. '
    'Populated by the orchestrator routing_output on RESULT envelopes; '
    'EMERGENCY envelopes pre-fill ER_NOW via the emergency_router.';

-- Force PostgREST to refresh its schema cache immediately. Supabase
-- also does this on a short schedule, but the NOTIFY shaves off the
-- 1-30s wait — useful when a deploy is blocked on this column
-- becoming visible.
NOTIFY pgrst, 'reload schema';
