-- patient_uploads — assets the patient sends in (selfie, voice memo, lab
-- scan, video clip) for AI analysis. Bytes are NOT persisted: the
-- backend hashes + dispatches to a Wiro AI service (moondream / whisper /
-- cogvlm / dots-ocr) and the *result text* lands on this row. The row
-- is the audit handle.
--
-- Why no bytes column / Storage bucket
--   1. KVKK posture: we don't hold patient images / audio at rest, so a
--      data-breach incident has a smaller blast radius.
--   2. Operations: skipping Supabase Storage means no bucket policy /
--      signed-URL / RLS to misconfigure.
--   3. AI integration: Wiro keeps the output URL for ~24h after the
--      task; if we ever need the original bytes we re-fetch from Wiro.
--
-- Tombstone integration
--   When DELETE /v1/me/sessions/{id} fires, the data_rights handler
--   tombstones every patient_uploads row pointing at that session in
--   the same way it tombstones the session itself: content columns
--   (sha256_hex, ai_result_text, ai_error) get NULLed; deleted_at +
--   deleted_reason set; row stays for cross-reference audit.
--
-- Run via Supabase SQL editor.

CREATE TABLE IF NOT EXISTS patient_uploads (
    asset_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id         uuid REFERENCES triage_sessions(id) ON DELETE SET NULL,

    -- Content metadata. NEVER the bytes.
    sha256_hex         text,
    content_type       text NOT NULL,        -- "image/jpeg", "audio/mp3", ...
    size_bytes         bigint NOT NULL,
    -- "image" | "audio" | "video" | "document"
    -- Drives the AI dispatcher in app/services/patient_upload_dispatcher.py
    upload_kind        text NOT NULL,

    -- KVKK consent. consent_to_process MUST be true for the BG task
    -- to fire; the route 422s when false. consent_text records what
    -- the patient was told the bytes would be used for ("hair-loss
    -- estimate", "transcription for clinical notes", ...).
    consent_to_process boolean NOT NULL,
    consent_text       text,

    -- Retention. Default 30 days from created_at, set by the route.
    -- A nightly cron (future) will tombstone rows past expires_at.
    expires_at         timestamptz NOT NULL,

    -- AI dispatch state machine.
    --   "pending"     row created, BG task not yet started
    --   "processing"  BG task running an AI provider
    --   "succeeded"   ai_result_text populated
    --   "failed"      ai_error populated
    -- Nudged forward by the dispatcher; exposed via
    -- GET /v1/patient/upload/{asset_id} polling.
    ai_status          text NOT NULL DEFAULT 'pending',
    ai_provider        text,                  -- "moondream"|"whisper"|"cogvlm"|"dots_ocr"
    ai_result_text     text,
    ai_error           text,
    ai_latency_ms      integer,
    processed_at       timestamptz,

    -- Tombstone (mirrors triage_sessions). NULL = live row.
    deleted_at         timestamptz,
    deleted_reason     text,
    created_at         timestamptz DEFAULT now()
);

-- Most lookups go through asset_id (PK) or session_id (KVKK delete).
CREATE INDEX IF NOT EXISTS patient_uploads_session_id_idx
    ON patient_uploads (session_id)
    WHERE deleted_at IS NULL;

-- The retention sweeper queries by expires_at, exclude tombstones.
CREATE INDEX IF NOT EXISTS patient_uploads_expires_at_idx
    ON patient_uploads (expires_at)
    WHERE deleted_at IS NULL;

-- Operator-side dedup lookup ("did this exact bytes blob arrive
-- before?") and forensic trace.
CREATE INDEX IF NOT EXISTS patient_uploads_sha256_idx
    ON patient_uploads (sha256_hex)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE patient_uploads IS
  'Patient-submitted assets for AI analysis. Bytes are NOT stored; only metadata + the AI result text. Tombstone-aware (deleted_at).';

COMMENT ON COLUMN patient_uploads.upload_kind IS
  'image | audio | video | document. Drives AI service selection in the dispatcher.';

COMMENT ON COLUMN patient_uploads.ai_status IS
  'pending | processing | succeeded | failed. Patient polls GET /v1/patient/upload/{asset_id} for transitions.';

COMMENT ON COLUMN patient_uploads.consent_to_process IS
  'KVKK opt-in. Route 422s when false; BG task only fires on true.';

COMMENT ON COLUMN patient_uploads.expires_at IS
  'Retention deadline. Default created_at + PATIENT_UPLOAD_RETENTION_DAYS. Nightly cron tombstones expired rows.';
