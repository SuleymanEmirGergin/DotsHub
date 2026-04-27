-- Retention purge function — KVKK Md.7 + GDPR Art.5(1)(e).
-- Policy + legal rationale: docs/RETENTION_POLICY.md.
-- Default windows match `app/core/config.py:RETENTION_DAYS_*`.
--
-- Two-stage session lifecycle:
--   1. Sessions older than `tombstone_days` whose content is still
--      live are tombstoned (PII columns NULL'd, deleted_at set with
--      reason='scheduled_retention'). The row stays for analytics
--      joins on session_id.
--   2. Tombstones older than `purge_days` (measured from deleted_at,
--      NOT created_at) are physically DELETE'd. This grace window
--      mirrors the user-initiated erasure path: a manual delete via
--      DELETE /v1/me/sessions/{id} also tombstones, and gets the same
--      `purge_days` window before disappearing — backups can be
--      restored within that window without re-resurrecting deleted
--      sessions.
--
-- Derived tables (events, llm_calls, feedback, push_tokens) are
-- single-stage: created_at-based DELETE.
--
-- Returns a one-row summary so the caller can log what was purged.
-- Idempotent: a second call same day deletes 0 rows (no overlap with
-- the prior run's window).
--
-- Run via Supabase SQL editor first to install. Schedule via:
--   - pg_cron (recommended; see RETENTION_POLICY.md option A), or
--   - GitHub Actions cron calling backend/scripts/run_retention_purge.py.

create or replace function public.app_retention_purge(
    tombstone_days   integer default 90,
    purge_days       integer default 90,
    events_days      integer default 90,
    llm_calls_days   integer default 30,
    feedback_days    integer default 365,
    push_tokens_days integer default 90,
    dry_run          boolean default false
)
returns table (
    sessions_tombstoned     bigint,
    sessions_purged         bigint,
    events_purged           bigint,
    llm_calls_purged        bigint,
    feedback_purged         bigint,
    push_tokens_purged      bigint,
    ran_at                  timestamptz,
    dry_run_used            boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_sessions_tombstoned bigint := 0;
    v_sessions_purged     bigint := 0;
    v_events_purged       bigint := 0;
    v_llm_calls_purged    bigint := 0;
    v_feedback_purged     bigint := 0;
    v_push_tokens_purged  bigint := 0;
begin
    if dry_run then
        -- Count what WOULD be affected without changing anything.
        select count(*) into v_sessions_tombstoned
            from triage_sessions
            where deleted_at is null
              and created_at < now() - make_interval(days => tombstone_days);

        select count(*) into v_sessions_purged
            from triage_sessions
            where deleted_at is not null
              and deleted_at < now() - make_interval(days => purge_days);

        select count(*) into v_events_purged
            from triage_events
            where created_at < now() - make_interval(days => events_days);

        select count(*) into v_llm_calls_purged
            from llm_calls
            where created_at < now() - make_interval(days => llm_calls_days);

        select count(*) into v_feedback_purged
            from triage_feedback
            where created_at < now() - make_interval(days => feedback_days);

        select count(*) into v_push_tokens_purged
            from push_tokens
            where updated_at < now() - make_interval(days => push_tokens_days);

        return query select
            v_sessions_tombstoned,
            v_sessions_purged,
            v_events_purged,
            v_llm_calls_purged,
            v_feedback_purged,
            v_push_tokens_purged,
            now(),
            true;
        return;
    end if;

    -- Stage 1: tombstone live-content sessions older than tombstone_days.
    -- Mirrors the column list in app/api/routes/data_rights.py — keep
    -- the two in sync if the schema gains a new PII column.
    with updated as (
        update triage_sessions
        set
            input_text                = null,
            answers                   = null,
            user_canonicals_tr        = null,
            asked_canonicals          = null,
            top_conditions            = null,
            doctor_ready_summary_tr   = null,
            why_specialty_tr          = null,
            specialty_scoring_debug   = null,
            confidence_debug          = null,
            emergency_reason_tr       = null,
            meta                      = null,
            deleted_at                = now(),
            deleted_reason            = 'scheduled_retention'
        where deleted_at is null
          and created_at < now() - make_interval(days => tombstone_days)
        returning 1
    )
    select count(*) into v_sessions_tombstoned from updated;

    -- Stage 2: physical delete of tombstones older than purge_days
    -- (measured from deleted_at — same grace for user erasure).
    with deleted as (
        delete from triage_sessions
        where deleted_at is not null
          and deleted_at < now() - make_interval(days => purge_days)
        returning 1
    )
    select count(*) into v_sessions_purged from deleted;

    -- Derived tables (single-stage).
    with deleted as (
        delete from triage_events
        where created_at < now() - make_interval(days => events_days)
        returning 1
    )
    select count(*) into v_events_purged from deleted;

    with deleted as (
        delete from llm_calls
        where created_at < now() - make_interval(days => llm_calls_days)
        returning 1
    )
    select count(*) into v_llm_calls_purged from deleted;

    with deleted as (
        delete from triage_feedback
        where created_at < now() - make_interval(days => feedback_days)
        returning 1
    )
    select count(*) into v_feedback_purged from deleted;

    with deleted as (
        delete from push_tokens
        where updated_at < now() - make_interval(days => push_tokens_days)
        returning 1
    )
    select count(*) into v_push_tokens_purged from deleted;

    return query select
        v_sessions_tombstoned,
        v_sessions_purged,
        v_events_purged,
        v_llm_calls_purged,
        v_feedback_purged,
        v_push_tokens_purged,
        now(),
        false;
end;
$$;

comment on function public.app_retention_purge(
    integer, integer, integer, integer, integer, integer, boolean
) is
'KVKK Md.7 / GDPR Art.5(1)(e) retention purge. See docs/RETENTION_POLICY.md.
 Two-stage sessions (tombstone -> purge); derived tables single-stage.
 Returns a one-row summary; pass dry_run := true to count without
 deleting. Defaults match backend/app/core/config.py RETENTION_DAYS_*.';

-- Example schedule via pg_cron (run after enabling the extension):
--
--   create extension if not exists pg_cron;
--   select cron.schedule(
--       'app_retention_daily',
--       '0 3 * * *',
--       $cron$select public.app_retention_purge()$cron$
--   );
--
-- Audit log of cron-triggered purge results lives in cron.job_run_details.
