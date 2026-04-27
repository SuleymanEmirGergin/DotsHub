-- Consent records — KVKK Md.6(2) + GDPR Art.9(2)(a) explicit consent.
-- Compliance lineage: COMPLIANCE_CHECK_2026_04.md:KR-1.
-- Privacy notice cross-reference: docs/PRIVACY_NOTICE.md (v0.2+).
--
-- Append-only audit trail. Every grant or withdrawal becomes a NEW
-- row; the "current state" is `ORDER BY created_at DESC LIMIT 1` for
-- a given (device_id, consent_type). We never UPDATE — that would
-- destroy the audit history that KVKK Md.12 + GDPR Art.7(1) require
-- (controller must be able to demonstrate that consent was given).
--
-- Two identifier columns:
--   device_id  : mobile UUID, present BEFORE any session is created
--                (intro screen consent fires here; no session yet).
--   session_id : populated when consent is collected mid-session
--                (e.g. push notification consent after first result).
-- One of the two must be present; the route enforces this.
--
-- consent_version + notice_version let us bump versions and force
-- re-acceptance: the mobile app compares its current target version
-- against the latest stored version for that device + type. A mis-
-- match means the consent is stale and the user must re-grant.
--
-- Run via Supabase SQL editor.

create table if not exists public.consent_records (
    id              bigserial primary key,
    device_id       text,
    session_id      uuid,
    consent_type    text not null,
    consent_version text not null,
    granted         boolean not null,
    locale          text not null default 'tr',
    notice_version  text,
    ip_hash         text,
    user_agent      text,
    created_at      timestamptz not null default now(),
    -- Audit invariant: at least one identifier must pin the record
    -- to a known device/session. Anonymous/unattributed consent rows
    -- have no audit value.
    constraint consent_records_has_identifier
        check (device_id is not null or session_id is not null)
);

-- Composite index for the hot read: "what is device X's current state
-- for consent type Y?" -> ORDER BY created_at DESC LIMIT 1.
create index if not exists ix_consent_records_device_type_ts
    on public.consent_records (device_id, consent_type, created_at desc)
    where device_id is not null;

-- Same shape for session-scoped lookups.
create index if not exists ix_consent_records_session_type_ts
    on public.consent_records (session_id, consent_type, created_at desc)
    where session_id is not null;

-- Helper function: current consent state for a (device, type) pair.
-- Returns NULL if no record exists. Used by the GET /v1/consent
-- handler and the retention purge query (verify nothing references a
-- session that's about to be tombstoned).
create or replace function public.consent_current_state(
    p_device_id      text,
    p_consent_type   text
)
returns table (
    granted          boolean,
    consent_version  text,
    notice_version   text,
    locale           text,
    granted_at       timestamptz
)
language sql
stable
as $$
    select
        granted,
        consent_version,
        notice_version,
        locale,
        created_at as granted_at
    from public.consent_records
    where device_id = p_device_id
      and consent_type = p_consent_type
    order by created_at desc
    limit 1;
$$;

comment on table public.consent_records is
'KVKK Md.6(2) + GDPR Art.9(2)(a) explicit consent audit trail.
 INSERT-only — every grant/withdrawal is a new row. Current state =
 latest row by (device_id, consent_type). See PRIVACY_NOTICE.md for
 the consent_type taxonomy (terms_general, health_data_processing,
 push_notifications, summary_email).';

comment on column public.consent_records.consent_version is
'Version of the specific consent text the user agreed to (e.g. v1.0).
 Bump when the consent text itself changes — forces re-acceptance.';

comment on column public.consent_records.notice_version is
'Version of the broader privacy notice in force when consent was
 given (e.g. v0.2). Tracks PRIVACY_NOTICE.md versioning so we can
 reconstruct exactly which document the user saw.';

-- Optional: retention. Consent records are an audit trail for the
-- LIFETIME of the user relationship — we DON'T auto-purge them on
-- the same schedule as session content. They follow the
-- organization's record-keeping policy (KVKK Kurumu may inspect for
-- 5+ years). The retention purge SQL in 20260427_retention_purge.sql
-- intentionally does not touch this table.
