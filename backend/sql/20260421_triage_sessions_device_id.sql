-- Link triage_sessions to push_tokens.device_id so follow-up
-- reminders can target the device that produced the session.
--
-- Nullable: existing rows get NULL; only sessions produced by an
-- app build that sends `device_id` will have the link. Follow-up
-- logic MUST handle NULL as "no push target".
--
-- Idempotent. Safe to rerun.

begin;

alter table public.triage_sessions
    add column if not exists device_id text;

-- Index for the follow-up join path:
--   sessions WHERE envelope_type='RESULT' AND created_at > cutoff
--   JOIN push_tokens ON push_tokens.device_id = sessions.device_id
-- Partial index keeps it tight — most sessions are RESULT by volume
-- but EMERGENCY/ERROR rows don't need the follow-up path.
create index if not exists ix_triage_sessions_device_id_created
    on public.triage_sessions(device_id, created_at desc)
    where device_id is not null;

commit;
