-- triage_sessions PII columns referenced by code but missing from
-- earlier schema migrations. Combines the deferred
-- 20260418_session_tombstone.sql apply with a drift-fix for
-- doctor_ready_summary_tr (added in app code in an unknown earlier
-- session but never captured as a SQL migration — surfaced when
-- 20260427_retention_purge.sql tried to NULL it during dry-run).
--
-- Idempotent: every ADD COLUMN uses IF NOT EXISTS so an environment
-- that already has any subset (e.g. a prod DB where these were added
-- via Supabase Dashboard SQL Editor without a migration file) won't
-- error.
--
-- Schema reach:
--   - data_rights.delete_my_session: writes NULL to all three on
--     erasure (the tombstone path).
--   - retention_purge.app_retention_purge: same NULL list during the
--     scheduled tombstone phase.
--   - medical_routing / orchestrator: write doctor_ready_summary_tr
--     when a clinical summary is produced.
--
-- Run via Supabase SQL editor or `apply_supabase_schema.py`.

ALTER TABLE public.triage_sessions
    ADD COLUMN IF NOT EXISTS deleted_at              timestamptz,
    ADD COLUMN IF NOT EXISTS deleted_reason          text,
    ADD COLUMN IF NOT EXISTS doctor_ready_summary_tr text;

-- Most analytics queries want to exclude tombstoned sessions.
-- Partial index keeps the live-set scan small without bloating the
-- main timestamp index.
CREATE INDEX IF NOT EXISTS idx_triage_sessions_live
    ON public.triage_sessions (created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN public.triage_sessions.deleted_at IS
  'User-initiated or retention-cron tombstone timestamp. NULL = live session.';
COMMENT ON COLUMN public.triage_sessions.deleted_reason IS
  'Tombstone reason. Current values: user_request, scheduled_retention.';
COMMENT ON COLUMN public.triage_sessions.doctor_ready_summary_tr IS
  'Localized (TR) doctor-ready summary produced by the medical_routing agent. NULLed during tombstone.';
