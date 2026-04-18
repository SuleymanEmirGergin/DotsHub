-- Audit trail for multi-tenant curated catalog edits.
-- Every admin write to /v1/admin/tenants/* writes a row here so we can
-- answer "who changed what when, and can we roll back?" after a bad
-- tenant config bricks a hospital's triage.
--
-- Design:
--   - One row per mutation (create / update).
--   - old_doc nullable (null on create).
--   - new_doc is the full JSON the endpoint wrote to the filesystem,
--     so recovery is "pick the pre-bad row and re-write that new_doc".
--   - actor is the admin user id (from admin_auth) when available,
--     nullable for system/CLI writes.
--
-- Run via Supabase SQL editor or psql.

CREATE TABLE IF NOT EXISTS tenant_catalog_audit (
    id          bigserial PRIMARY KEY,
    tenant_id   text NOT NULL,
    action      text NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    actor       text,
    old_doc     jsonb,
    new_doc     jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_catalog_audit_tenant_created
    ON tenant_catalog_audit (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_catalog_audit_created
    ON tenant_catalog_audit (created_at DESC);

COMMENT ON TABLE tenant_catalog_audit IS
  'Immutable audit log of curated_conditions.<tenant>.json writes from the admin API.';
COMMENT ON COLUMN tenant_catalog_audit.old_doc IS
  'Catalog document before the write. NULL on create actions.';
COMMENT ON COLUMN tenant_catalog_audit.new_doc IS
  'Catalog document written to disk. Use this for rollback: pick a known-good row and re-apply new_doc.';
