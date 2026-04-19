-- admin_users — row-level-security + self-read policy.
--
-- Why: `dashboard/lib/supabaseServerAuthed.ts` uses the anon key with
-- the caller's session cookie to read `public.admin_users`. Supabase
-- defaults new public-schema tables to RLS-enabled (with no policy),
-- which makes every SELECT return zero rows — so `requireAdmin()`
-- bounces the just-authenticated user to `/login?e=not_admin` even
-- when their admin_users row exists.
--
-- The policy below grants an authenticated user the right to SELECT
-- exactly their own admin_users row (by `user_id = auth.uid()`).
-- Writes stay service-role-only; other users' rows stay invisible.
--
-- Safe to run repeatedly (idempotent).

begin;

alter table public.admin_users enable row level security;

drop policy if exists "admin_users_self_read" on public.admin_users;

create policy "admin_users_self_read"
on public.admin_users
for select
to authenticated
using (user_id = auth.uid());

commit;
