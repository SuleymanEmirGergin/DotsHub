-- Audit log — append-only WORM (Write Once, Read Many).
-- Compliance lineage: DPIA_2026.md:R-10. KVKK Md.12 (data security
-- + breach evidence) and GDPR Art.30 (records of processing) both
-- require demonstrable evidence; this table is the central log.
--
-- Distinct from existing tables:
--   - triage_events: per-turn activity, retention 90 days, contains
--     operational details (envelope_type, rule_id, etc).
--   - tenant_catalog_audit: admin catalog mutations only.
--   - consent_records: explicit consent state, INSERT-only by route
--     discipline but no DB-level guard.
-- audit_log is the SUPER-set: a forensic trail across surfaces
-- (data_rights, consent, admin actions, rule changes, security
-- incidents) with longer retention (730 days, not auto-purged).
--
-- WORM enforcement:
--   1. Triggers below raise on UPDATE / DELETE — blocks ALL writers
--      including service_role unless someone DROPs the triggers
--      with superuser privilege.
--   2. retention purge SQL (20260427_retention_purge.sql)
--      intentionally does NOT include this table — see the comment
--      block in that file. A future cron-triggered purge of rows
--      older than 730 days would be a separate function.
--
-- Schema design:
--   - event_type uses the dotted "domain.verb" namespace
--     (e.g. data_rights.session_tombstoned, consent.recorded,
--     admin.tenant_catalog_updated). Keeps queries readable and
--     supports prefix filters (event_type LIKE 'consent.%').
--   - actor_type ∈ {user, admin, system, cron}. The actor_id is the
--     anonymised UUID (device_id, admin user_id) — NEVER raw PII
--     and NEVER raw IP (ip_hash column carries the salted hash).
--   - target_id is the resource the event applied to: session_id
--     for data_rights, device_id for consent, tenant_id for admin.
--   - payload is JSONB metadata (counts, status flags, version
--     strings). MUST NOT contain free-text symptoms, names, emails,
--     or any other PII — module-level discipline (`app/audit.py`)
--     enforces this.
--
-- Run via Supabase SQL editor or `apply_supabase_schema.py`.

create table if not exists public.audit_log (
    id          bigserial primary key,
    event_type  text not null,
    actor_type  text not null check (actor_type in ('user', 'admin', 'system', 'cron')),
    actor_id    text,
    target_id   text,
    severity    text not null default 'info'
                check (severity in ('info', 'warning', 'critical')),
    payload     jsonb not null default '{}'::jsonb,
    ip_hash     text,
    created_at  timestamptz not null default now()
);

-- Hot reads:
-- 1. "what events of type X happened in window Y?"
-- 2. "what did actor A do?"
-- 3. "what events touched resource R?"
create index if not exists idx_audit_log_type_created
    on public.audit_log (event_type, created_at desc);
create index if not exists idx_audit_log_actor_created
    on public.audit_log (actor_id, created_at desc)
    where actor_id is not null;
create index if not exists idx_audit_log_target_created
    on public.audit_log (target_id, created_at desc)
    where target_id is not null;
create index if not exists idx_audit_log_critical
    on public.audit_log (created_at desc)
    where severity = 'critical';

-- WORM enforcement at the table level. Triggers fire BEFORE the
-- UPDATE/DELETE so the modification never lands. service_role can
-- still INSERT, which is what the route layer uses; everything
-- mutating raises.
create or replace function public.audit_log_block_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception
        'audit_log is append-only (WORM); UPDATE and DELETE are forbidden. '
        'See docs/DPIA_2026.md:R-10 + RETENTION_POLICY.md.';
end;
$$;

drop trigger if exists audit_log_block_update on public.audit_log;
create trigger audit_log_block_update
    before update on public.audit_log
    for each row execute function public.audit_log_block_mutation();

drop trigger if exists audit_log_block_delete on public.audit_log;
create trigger audit_log_block_delete
    before delete on public.audit_log
    for each row execute function public.audit_log_block_mutation();

comment on table public.audit_log is
'Append-only forensic audit log (WORM). UPDATE/DELETE blocked by
 trigger. Retention 730 days, NOT included in app_retention_purge().
 See docs/DPIA_2026.md:R-10 and docs/RETENTION_POLICY.md.';

comment on column public.audit_log.event_type is
'Dotted namespace: domain.verb. Examples: data_rights.session_tombstoned,
 consent.recorded, admin.tenant_catalog_updated, security.breach_detected,
 system.retention_purge_completed.';

comment on column public.audit_log.payload is
'JSONB metadata only — counts, status flags, version strings, rule
 ids. MUST NOT contain free-text symptoms, names, emails, or any
 other PII. The application layer (app/audit.py) enforces this.';
