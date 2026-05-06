-- Per-clause consent audit log.
--
-- KVKK Art. 6 explicit consent for special-category health data must be
-- demonstrable on demand: which clause did the user accept, in which
-- notice / consent version, and at what time. Until now we tracked a
-- single "I accept" boolean in the mobile app's session store and
-- never persisted it. With the three-checkbox onboarding (mobile #36 —
-- terms / KVKK / 13+) we now have per-clause toggles; this table records
-- one row per toggle so audits can reconstruct the user's intent timeline.
--
-- One row per checkbox tap, including un-ticks (accepted = false). The
-- audit-trail value is the *sequence*; the latest row per (device_id,
-- clause_id) is the effective state.
--
-- PII consideration: device_id is anonymous (random UUID provisioned
-- locally on first launch — see mobile/utils/deviceId.ts). user_agent
-- and ip_hash are optional and OFF by default at the route level —
-- enabling them is a Privacy-team gate, not a developer call.
--
-- Safe to run multiple times (idempotent).

begin;

create table if not exists public.consent_events (
    id bigserial primary key,
    device_id text not null,
    clause_id text not null,
    accepted boolean not null,
    notice_version text not null,
    consent_version text not null,
    -- Optional client metadata. NULL by default so a privacy
    -- regression doesn't suddenly start collecting fingerprints.
    user_agent text,
    ip_hash text,
    created_at timestamptz not null default now(),
    constraint consent_events_clause_id_check
        check (clause_id in ('terms', 'kvkk', 'age'))
);

-- "Latest state per device per clause" query — KVKK auditor's main
-- access pattern. The descending created_at lets `LIMIT 1` walk the
-- index instead of a full sort.
create index if not exists ix_consent_events_device_clause_created
    on public.consent_events(device_id, clause_id, created_at desc);

-- Coarse "all events for this device" — right-to-be-forgotten
-- tombstoning needs to scan + null these out alongside triage_sessions.
create index if not exists ix_consent_events_device_id
    on public.consent_events(device_id);

commit;
