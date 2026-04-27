-- Operator review state machine columns for patient_uploads.
--
-- Adds reviewer_* columns + a review_status enum that the operator
-- dashboard transitions via PATCH /v1/admin/uploads/{asset_id}/review.
-- State machine is REVERSIBLE — operator can correct mistakes by
-- moving back to pending_review or sideways between approved /
-- rejected / needs_followup.
--
-- Why DEFAULT 'pending_review' on existing rows: any upload that
-- arrived BEFORE this migration ran is implicitly awaiting review;
-- making the operator queue render them as "pending_review" gives a
-- consistent backlog without a manual backfill.
--
-- Run via Supabase SQL editor.

ALTER TABLE patient_uploads
    ADD COLUMN IF NOT EXISTS review_status   text NOT NULL DEFAULT 'pending_review',
    ADD COLUMN IF NOT EXISTS reviewer_notes  text,
    ADD COLUMN IF NOT EXISTS reviewed_at     timestamptz,
    ADD COLUMN IF NOT EXISTS reviewed_by     text;

-- Operator dashboard's primary filter -- exclude tombstoned + index
-- to make the "all pending_review uploads" query O(log n).
CREATE INDEX IF NOT EXISTS patient_uploads_review_status_idx
    ON patient_uploads (review_status, created_at DESC)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN patient_uploads.review_status IS
  'pending_review (default) | approved | rejected | needs_followup. Reversible state machine driven by PATCH /v1/admin/uploads/{asset_id}/review.';

COMMENT ON COLUMN patient_uploads.reviewed_by IS
  'Operator email when an operator key authed; "admin" when ADMIN_API_KEY (super-admin) authed.';

COMMENT ON COLUMN patient_uploads.reviewer_notes IS
  'Operator-visible free-text rationale for the review decision. Cleared on KVKK tombstone.';
