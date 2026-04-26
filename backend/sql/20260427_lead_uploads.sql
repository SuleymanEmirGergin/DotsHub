-- lead_uploads — operator-curated bag table linking patient uploads
-- to a health-tourism lead.
--
-- Why a bag table (not a JSONB array on health_tourism_leads):
--   1. Foreign keys catch dangling references at write time
--   2. Diff-based replace preserves linked_at + linked_by_operator_id
--      on links the operator left untouched (audit trail intact)
--   3. KVKK / forensic queries ("which operator linked which asset
--      to which lead, when?") run cleanly without JSONB introspection
--
-- Replace semantics: PATCH /v1/admin/leads/{lead_id}/uploads diffs
-- the desired set against the current LIVE links and:
--   - INSERTs new ones (fresh linked_at + linked_by_operator_id)
--   - TOMBSTONEs removed ones (deleted_at + deleted_reason set;
--     row stays for audit, never physically deleted)
--   - LEAVES untouched links unchanged (history preserved)
--
-- Cross-session OK: an operator can link uploads from session A and
-- session B to the same lead (manual review consolidation use case).
-- The schema does NOT enforce session-coupling.
--
-- Run via Supabase SQL editor.

CREATE TABLE IF NOT EXISTS lead_uploads (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- health_tourism_leads.id is text (clinic-prefixed slug + UUID)
    -- so lead_id is text here too. ON DELETE CASCADE: lead row
    -- physical-delete (Madde 10 5-year retention will eventually
    -- expire) cleans the link bag with it.
    lead_id                 text NOT NULL
        REFERENCES health_tourism_leads(id) ON DELETE CASCADE,

    -- patient_uploads.asset_id is uuid. ON DELETE CASCADE: hard-
    -- delete of an asset row also drops links pointing to it.
    -- Tombstone (deleted_at) on the upload does NOT cascade --
    -- the link stays so the operator dashboard can see "this lead
    -- USED to have a Norwood image attached, deleted at <ts>".
    asset_id                uuid NOT NULL
        REFERENCES patient_uploads(asset_id) ON DELETE CASCADE,

    linked_at               timestamptz DEFAULT now(),
    -- "admin" for super-admin authed; operator email for operator
    -- key authed. Stored as text -- matches the reviewed_by
    -- convention on patient_uploads, decoupled from any future
    -- operator user table FK.
    linked_by_operator_id   text NOT NULL,

    -- Tombstone (mirrors patient_uploads / triage_sessions). NULL
    -- = live link.
    deleted_at              timestamptz,
    deleted_reason          text
);

-- A live link (lead, asset) pair must be unique. Re-linking after
-- removal is allowed because the previous row is tombstoned (NOT
-- in the partial index) and the new row gets a fresh id.
CREATE UNIQUE INDEX IF NOT EXISTS lead_uploads_lead_asset_live_uniq
    ON lead_uploads (lead_id, asset_id)
    WHERE deleted_at IS NULL;

-- Hot-path lookup for the "uploads attached to lead X" query.
CREATE INDEX IF NOT EXISTS lead_uploads_lead_id_live_idx
    ON lead_uploads (lead_id, linked_at DESC)
    WHERE deleted_at IS NULL;

-- Reverse lookup ("which leads is this asset linked to" -- forensic).
CREATE INDEX IF NOT EXISTS lead_uploads_asset_id_idx
    ON lead_uploads (asset_id)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE lead_uploads IS
  'Operator-curated bag linking patient uploads to health-tourism leads. Tombstone-aware (deleted_at).';

COMMENT ON COLUMN lead_uploads.linked_by_operator_id IS
  '"admin" for super-admin authed; operator email otherwise. Mirrors patient_uploads.reviewed_by.';
