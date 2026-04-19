-- Feedback acknowledge / actioned flow.
-- Adds columns to triage_feedback so admins can mark feedback as
-- seen + note what was done (e.g. "added synonym variant in PR #123").
--
-- Read path: admin/feedback page filters by ack status.
-- Write path: POST /v1/admin/feedback/{id}/ack sets
-- acknowledged_at + acknowledged_by + (optional) ack_note.
--
-- Run via Supabase SQL editor.

ALTER TABLE triage_feedback
    ADD COLUMN IF NOT EXISTS acknowledged_at  timestamptz,
    ADD COLUMN IF NOT EXISTS acknowledged_by  text,
    ADD COLUMN IF NOT EXISTS ack_note         text;

CREATE INDEX IF NOT EXISTS idx_triage_feedback_ack_status
    ON triage_feedback (acknowledged_at)
    WHERE acknowledged_at IS NULL;  -- partial index: fast "inbox" query

COMMENT ON COLUMN triage_feedback.acknowledged_at IS
  'When admin marked this feedback as seen+actioned. NULL = in the inbox.';
COMMENT ON COLUMN triage_feedback.acknowledged_by IS
  'Admin user_id who acknowledged. Free text; matches admin_users.id.';
COMMENT ON COLUMN triage_feedback.ack_note IS
  'Short note on what was done (PR link / synonym change / rule update). Optional.';
