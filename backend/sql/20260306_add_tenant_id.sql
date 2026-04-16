-- Multi-tenant: add tenant_id to triage tables (Faz 1: single-tenant triage, admin tenant-aware).
-- Safe to run after 20260210_supabase_triage_schema.sql.

begin;

-- triage_sessions
alter table public.triage_sessions
    add column if not exists tenant_id text not null default 'default';

update public.triage_sessions set tenant_id = 'default' where tenant_id is null or tenant_id = '';

create index if not exists ix_triage_sessions_tenant_id
    on public.triage_sessions(tenant_id);

-- triage_events
alter table public.triage_events
    add column if not exists tenant_id text not null default 'default';

update public.triage_events set tenant_id = 'default' where tenant_id is null or tenant_id = '';

create index if not exists ix_triage_events_tenant_id
    on public.triage_events(tenant_id);

-- triage_feedback
alter table public.triage_feedback
    add column if not exists tenant_id text not null default 'default';

update public.triage_feedback set tenant_id = 'default' where tenant_id is null or tenant_id = '';

create index if not exists ix_triage_feedback_tenant_id
    on public.triage_feedback(tenant_id);

-- tuning_tasks (if table exists)
do $$
begin
    if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'tuning_tasks') then
        alter table public.tuning_tasks add column if not exists tenant_id text not null default 'default';
        update public.tuning_tasks set tenant_id = 'default' where tenant_id is null or tenant_id = '';
        create index if not exists ix_tuning_tasks_tenant_id on public.tuning_tasks(tenant_id);
    end if;
end
$$;

commit;
