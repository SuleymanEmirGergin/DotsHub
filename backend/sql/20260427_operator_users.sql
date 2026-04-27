-- operator_users — dashboard operators with per-user API keys.
--
-- Each operator gets a 32-byte hex API key shown ONCE at create
-- time. Only the SHA-256 hash is persisted; lookup is constant-time
-- via hash compare. Lost key -> rotate (deactivate + recreate);
-- rotation endpoint deferred to a later session.
--
-- Roles (3-tier hierarchy enforced in app/admin_auth.py):
--   reviewer  — can list + review uploads (default)
--   manager   — reviewer + can link uploads to leads
--   admin     — manager + can manage other operators
--
-- The legacy ADMIN_API_KEY env var is preserved as a "super-admin"
-- bypass — it always passes role checks and never appears in this
-- table. Operator user table is purely additive.
--
-- Run via Supabase SQL editor.

CREATE TABLE IF NOT EXISTS operator_users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text NOT NULL,
    full_name       text NOT NULL,
    -- SHA-256 hex of the plaintext API key. 64 chars; UNIQUE so a
    -- collision (astronomically unlikely with 32-byte input) surfaces
    -- as a duplicate-key error rather than authenticating the wrong
    -- operator.
    api_key_hash    text NOT NULL UNIQUE,
    -- 'reviewer' | 'manager' | 'admin'. Application-layer enforces
    -- the hierarchy; DB stores the literal string for forward
    -- compatibility with future roles.
    role            text NOT NULL DEFAULT 'reviewer',
    deactivated_at  timestamptz,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- Email is unique only among LIVE operators — re-creating with the
-- same email after deactivation is allowed (e.g. someone leaves and
-- a new hire reuses their corporate email).
CREATE UNIQUE INDEX IF NOT EXISTS operator_users_email_live_uniq
    ON operator_users (email)
    WHERE deactivated_at IS NULL;

-- Hot-path lookup on every operator-authed request.
CREATE INDEX IF NOT EXISTS operator_users_api_key_hash_live_idx
    ON operator_users (api_key_hash)
    WHERE deactivated_at IS NULL;

COMMENT ON TABLE operator_users IS
  'Dashboard operators (per-user API keys). ADMIN_API_KEY env stays separate as super-admin bypass.';

COMMENT ON COLUMN operator_users.api_key_hash IS
  'SHA-256 hex of plaintext API key. Plaintext shown once at create; lost key -> deactivate + recreate.';

COMMENT ON COLUMN operator_users.role IS
  'reviewer | manager | admin. Hierarchy enforced in app/admin_auth.require_min_role.';

COMMENT ON COLUMN operator_users.deactivated_at IS
  'Soft delete. Lookup index excludes deactivated rows so the operator can no longer authenticate.';
