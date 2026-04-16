-- Push notification token storage.
-- Safe to run multiple times (idempotent).

begin;

create table if not exists public.push_tokens (
    id bigserial primary key,
    device_id text not null,
    expo_token text not null,
    platform text not null default 'unknown',
    locale text not null default 'tr-TR',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Upsert by device_id
create unique index if not exists ux_push_tokens_device_id
    on public.push_tokens(device_id);

create index if not exists ix_push_tokens_active
    on public.push_tokens(active) where active = true;

commit;
