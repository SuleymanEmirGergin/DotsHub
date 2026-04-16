-- Admin users management table.
-- Uses Supabase Auth user_id as foreign key.
-- Safe to run multiple times (idempotent).

begin;

create table if not exists public.admin_users (
    id bigserial primary key,
    user_id uuid not null unique,
    email text not null,
    role text not null default 'admin',
    created_at timestamptz not null default now()
);

-- Role check
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'chk_admin_users_role'
    ) then
        alter table public.admin_users
        add constraint chk_admin_users_role
        check (role in ('admin', 'super_admin'));
    end if;
exception when others then
    raise notice 'Skipping admin_users role check: %', sqlerrm;
end
$$;

create index if not exists ix_admin_users_email on public.admin_users(email);

commit;
