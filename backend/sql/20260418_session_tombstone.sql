-- Session tombstone columns for KVKK / GDPR right-to-delete.
-- DELETE /v1/me/sessions/{id} wipes content + derived rows but
-- keeps the session row with deleted_at + deleted_reason set, so
-- analytics joins on session_id don't break.
--
-- Run via Supabase SQL editor.

ALTER TABLE triage_sessions
    ADD COLUMN IF NOT EXISTS deleted_at     timestamptz,
    ADD COLUMN IF NOT EXISTS deleted_reason text;

-- Partial index: most analytics queries want to exclude tombstones.
CREATE INDEX IF NOT EXISTS idx_triage_sessions_live
    ON triage_sessions (created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN triage_sessions.deleted_at IS
  'User-initiated tombstone timestamp. NULL = live session. Not the same as physical row delete.';
COMMENT ON COLUMN triage_sessions.deleted_reason IS
  'Free-text reason. Current values: user_request (KVKK/GDPR right-to-delete), scheduled_retention (future cron).';
