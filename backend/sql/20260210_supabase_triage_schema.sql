-- Supabase schema for deterministic triage pipeline.
-- Safe to run multiple times (idempotent).

begin;

create extension if not exists pgcrypto;

create table if not exists public.triage_sessions (
    id uuid primary key default gen_random_uuid(),
    session_id uuid unique,
    locale text not null default 'tr-TR',
    input_text text not null default '',
    answers jsonb not null default '{}'::jsonb,
    asked_canonicals jsonb not null default '[]'::jsonb,
    envelope_type text not null default 'QUESTION',
    turn_index integer not null default 0,
    recommended_specialty_id text,
    recommended_specialty_tr text,
    confidence_0_1 double precision,
    confidence_label_tr text,
    confidence_explain_tr text,
    stop_reason text,
    extracted_canonicals jsonb not null default '[]'::jsonb,
    user_canonicals_tr jsonb not null default '[]'::jsonb,
    top_conditions jsonb not null default '[]'::jsonb,
    why_specialty_tr jsonb not null default '[]'::jsonb,
    specialty_scoring_debug jsonb not null default '{}'::jsonb,
    question_selector_debug jsonb not null default '{}'::jsonb,
    confidence_debug jsonb not null default '{}'::jsonb,
    emergency_rule_id text,
    emergency_reason_tr text,
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.triage_sessions add column if not exists id uuid default gen_random_uuid();
alter table public.triage_sessions add column if not exists session_id uuid;
alter table public.triage_sessions add column if not exists locale text default 'tr-TR';
alter table public.triage_sessions add column if not exists input_text text default '';
alter table public.triage_sessions add column if not exists answers jsonb default '{}'::jsonb;
alter table public.triage_sessions add column if not exists asked_canonicals jsonb default '[]'::jsonb;
alter table public.triage_sessions add column if not exists envelope_type text default 'QUESTION';
alter table public.triage_sessions add column if not exists turn_index integer default 0;
alter table public.triage_sessions add column if not exists recommended_specialty_id text;
alter table public.triage_sessions add column if not exists recommended_specialty_tr text;
alter table public.triage_sessions add column if not exists confidence_0_1 double precision;
alter table public.triage_sessions add column if not exists confidence_label_tr text;
alter table public.triage_sessions add column if not exists confidence_explain_tr text;
alter table public.triage_sessions add column if not exists stop_reason text;
alter table public.triage_sessions add column if not exists extracted_canonicals jsonb default '[]'::jsonb;
alter table public.triage_sessions add column if not exists user_canonicals_tr jsonb default '[]'::jsonb;
alter table public.triage_sessions add column if not exists top_conditions jsonb default '[]'::jsonb;
alter table public.triage_sessions add column if not exists why_specialty_tr jsonb default '[]'::jsonb;
alter table public.triage_sessions add column if not exists specialty_scoring_debug jsonb default '{}'::jsonb;
alter table public.triage_sessions add column if not exists question_selector_debug jsonb default '{}'::jsonb;
alter table public.triage_sessions add column if not exists confidence_debug jsonb default '{}'::jsonb;
alter table public.triage_sessions add column if not exists emergency_rule_id text;
alter table public.triage_sessions add column if not exists emergency_reason_tr text;
alter table public.triage_sessions add column if not exists meta jsonb default '{}'::jsonb;
alter table public.triage_sessions add column if not exists created_at timestamptz default now();
alter table public.triage_sessions add column if not exists updated_at timestamptz default now();

update public.triage_sessions
set session_id = id
where session_id is null and id is not null;

create unique index if not exists ux_triage_sessions_session_id
    on public.triage_sessions(session_id);
create index if not exists ix_triage_sessions_created_at
    on public.triage_sessions(created_at desc);
create index if not exists ix_triage_sessions_updated_at
    on public.triage_sessions(updated_at desc);
create index if not exists ix_triage_sessions_envelope_type
    on public.triage_sessions(envelope_type);
create index if not exists ix_triage_sessions_stop_reason
    on public.triage_sessions(stop_reason);
create index if not exists ix_triage_sessions_confidence
    on public.triage_sessions(confidence_0_1);

create or replace function public.triage_set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_triage_sessions_set_updated_at on public.triage_sessions;
create trigger trg_triage_sessions_set_updated_at
before update on public.triage_sessions
for each row execute function public.triage_set_updated_at();

create or replace function public.triage_sessions_sync_ids_and_canonicals()
returns trigger
language plpgsql
as $$
begin
    if new.id is null then
        new.id = gen_random_uuid();
    end if;

    if new.session_id is null then
        new.session_id = new.id;
    end if;

    if new.user_canonicals_tr is null and new.extracted_canonicals is not null then
        new.user_canonicals_tr = new.extracted_canonicals;
    end if;

    if new.extracted_canonicals is null and new.user_canonicals_tr is not null then
        new.extracted_canonicals = new.user_canonicals_tr;
    end if;

    if new.extracted_canonicals = '[]'::jsonb and new.user_canonicals_tr is not null and new.user_canonicals_tr <> '[]'::jsonb then
        new.extracted_canonicals = new.user_canonicals_tr;
    end if;

    if new.user_canonicals_tr = '[]'::jsonb and new.extracted_canonicals is not null and new.extracted_canonicals <> '[]'::jsonb then
        new.user_canonicals_tr = new.extracted_canonicals;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_triage_sessions_sync_ids_and_canonicals on public.triage_sessions;
create trigger trg_triage_sessions_sync_ids_and_canonicals
before insert or update on public.triage_sessions
for each row execute function public.triage_sessions_sync_ids_and_canonicals();

create table if not exists public.triage_events (
    id bigserial primary key,
    session_id uuid not null,
    event_type text,
    event text,
    payload jsonb not null default '{}'::jsonb,
    data jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

alter table public.triage_events add column if not exists id bigserial;
alter table public.triage_events add column if not exists session_id uuid;
alter table public.triage_events add column if not exists event_type text;
alter table public.triage_events add column if not exists event text;
alter table public.triage_events add column if not exists payload jsonb default '{}'::jsonb;
alter table public.triage_events add column if not exists data jsonb default '{}'::jsonb;
alter table public.triage_events add column if not exists created_at timestamptz default now();

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'fk_triage_events_session_id'
    ) then
        alter table public.triage_events
        add constraint fk_triage_events_session_id
        foreign key (session_id)
        references public.triage_sessions(id)
        on delete cascade;
    end if;
exception when others then
    raise notice 'Skipping triage_events FK creation: %', sqlerrm;
end
$$;

create index if not exists ix_triage_events_session_id
    on public.triage_events(session_id);
create index if not exists ix_triage_events_created_at
    on public.triage_events(created_at desc);

create or replace function public.triage_events_sync_legacy_columns()
returns trigger
language plpgsql
as $$
begin
    if new.event_type is null and new.event is not null then
        new.event_type = new.event;
    end if;
    if new.event is null and new.event_type is not null then
        new.event = new.event_type;
    end if;
    if new.payload is null and new.data is not null then
        new.payload = new.data;
    end if;
    if new.data is null and new.payload is not null then
        new.data = new.payload;
    end if;
    if new.payload is null then
        new.payload = '{}'::jsonb;
    end if;
    if new.data is null then
        new.data = '{}'::jsonb;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_triage_events_sync_legacy_columns on public.triage_events;
create trigger trg_triage_events_sync_legacy_columns
before insert or update on public.triage_events
for each row execute function public.triage_events_sync_legacy_columns();

create table if not exists public.triage_feedback (
    id bigserial primary key,
    session_id uuid not null,
    rating text not null,
    comment text,
    user_selected_specialty_id text,
    created_at timestamptz not null default now()
);

alter table public.triage_feedback add column if not exists id bigserial;
alter table public.triage_feedback add column if not exists session_id uuid;
alter table public.triage_feedback add column if not exists rating text;
alter table public.triage_feedback add column if not exists comment text;
alter table public.triage_feedback add column if not exists user_selected_specialty_id text;
alter table public.triage_feedback add column if not exists created_at timestamptz default now();

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'fk_triage_feedback_session_id'
    ) then
        alter table public.triage_feedback
        add constraint fk_triage_feedback_session_id
        foreign key (session_id)
        references public.triage_sessions(id)
        on delete cascade;
    end if;
exception when others then
    raise notice 'Skipping triage_feedback FK creation: %', sqlerrm;
end
$$;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'chk_triage_feedback_rating'
    ) then
        alter table public.triage_feedback
        add constraint chk_triage_feedback_rating
        check (rating in ('up', 'down'));
    end if;
exception when others then
    raise notice 'Skipping triage_feedback rating check creation: %', sqlerrm;
end
$$;

create index if not exists ix_triage_feedback_session_id
    on public.triage_feedback(session_id);
create index if not exists ix_triage_feedback_created_at
    on public.triage_feedback(created_at desc);

commit;
