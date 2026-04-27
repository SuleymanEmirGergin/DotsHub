# Dashboard E2E Tests

Two suites, one Playwright install.

| Suite | Target | When it runs | Command |
|---|---|---|---|
| `localhost/` | Local `next dev` on :3002 | Day-to-day, existing `dashboard-tests` CI | `pnpm test:e2e` |
| `staging/` | Deployed dashboard + live staging Supabase | Manual / release gate | `pnpm test:e2e:staging` |

## Localhost mode

No setup. `pnpm test:e2e` boots the dev server (or reuses a running one) and runs the smoke tests in `e2e/localhost/`. These tests are resilient to auth state — they accept either the login page or the admin content.

## Staging mode (live Supabase)

Against a real staging Supabase project: real auth, real rows. Every test run seeds data, exercises the app, then deletes everything it created.

### One-time setup

1. Copy the env template:

   ```bash
   cp dashboard/.env.staging.example dashboard/.env.staging
   ```

2. Fill in (the file is gitignored):
   - `PLAYWRIGHT_BASE_URL` — deployed dashboard URL (no trailing slash)
   - `STAGING_SUPABASE_URL` — staging project URL
   - `STAGING_SUPABASE_ANON_KEY` — public anon key
   - `STAGING_SUPABASE_SERVICE_ROLE_KEY` — service role key (used by setup/teardown only)
   - `STAGING_TEST_ADMIN_EMAIL` — throwaway admin inbox

3. Make sure the staging Supabase has the migrations applied:

   ```
   backend/sql/20260210_supabase_triage_schema.sql
   backend/sql/20260214_admin_users.sql
   ```

### Run

```bash
pnpm test:e2e:staging          # headless
pnpm test:e2e:staging:ui       # interactive
```

### What happens

1. `globalSetup`:
   - Loads `.env.staging`
   - Generates a run id (`E2E_RUN_ID=<timestamp>-<rand>`)
   - Sweeps `triage_sessions` rows marked `meta.e2e_test=true` older than 60 min (leaked from crashed runs)
   - Provisions the test admin (`auth.users` + `admin_users`) — idempotent
   - Seeds 5 triage_sessions rows, each tagged `meta.e2e_test_run_id=<run_id>`
   - Writes `e2e/.run-state.json` (gitignored) so specs can look up seeded ids

2. Tests:
   - Authenticate via `auth.admin.generateLink({ type: "magiclink" })` — real PKCE flow, no email delivery
   - Hit the deployed dashboard, walk the admin screens, assert on seeded labels

3. `globalTeardown`:
   - Deletes every `triage_sessions` row with `meta.e2e_test_run_id=<run_id>`
   - Cascade FKs remove matching `triage_events` + `triage_feedback`
   - Removes `.run-state.json`

### Tradeoffs we picked

- **Data isolation via `meta.e2e_test_run_id`** (prefix+cleanup). Non-destructive to other staging usage. Leaked rows are identifiable (`meta.e2e_test=true`) and cleaned by the stale sweep on the next run.
- **Programmatic magic link** (Service Role `admin.generateLink`) — no SMTP dependency, no email-rate-limit games. Still exercises the real callback + PKCE code path.
- **Serial execution** (`fullyParallel: false` in the staging project + `workers: 1`) — we share one DB, so interleaved writes would race.
- **One global admin user**, reused across runs — provisioning is idempotent, so parallel/repeated runs don't duplicate rows.

### CI

`.github/workflows/dashboard-tests.yml` has a separate `e2e-staging` job that runs on **`workflow_dispatch` + `include_staging=true`** AND on a **nightly cron (06:00 UTC)**. Required repository secrets:

- `STAGING_SUPABASE_URL`
- `STAGING_SUPABASE_ANON_KEY`
- `STAGING_SUPABASE_SERVICE_ROLE_KEY`
- `STAGING_BASE_URL` — deployed URL; see alias note below
- `STAGING_TEST_ADMIN_EMAIL`
- `VERCEL_AUTOMATION_BYPASS_SECRET` — Vercel Protection Bypass for Automation token (generated in Vercel → Settings → Deployment Protection)

Trigger manually: `gh workflow run dashboard-tests.yml --ref <branch> -f include_staging=true` or via Actions UI.

### Stable `STAGING_BASE_URL` via Vercel alias

Per-commit Vercel preview URLs embed the deployment hash and change on every build, so hard-coding one into `STAGING_BASE_URL` means the secret goes stale every push. Fix this **once** in Vercel:

1. Vercel → TriAIge project → Deployments → pick the preview deployment you want the nightly cron to target (usually the one tracking `main`, i.e. the most recent production deployment).
2. Click the deployment → **Domains** tab → **Add Domain** → pick a subdomain you control (e.g. `dots-hub-staging.vercel.app` if free, or any custom domain you own). Vercel will promote the alias to always point at the latest deployment for the chosen branch.
3. Update the `STAGING_BASE_URL` repo secret to that alias — it now stays valid regardless of how many PRs deploy.

Alternative: if you already use a production alias (e.g. `dots-hub.vercel.app`), point the nightly job there — production is the source of truth the regression should catch anyway.

### Adding a new staging test

1. Put it in `e2e/staging/*.spec.ts` so Playwright's `staging` project picks it up.
2. If it needs seeded data, reference `readRunState()` + `findSeeded(state, "<label>")` from `helpers/runState.ts`.
3. If it needs auth, call `signInAsAdmin(page)` (copy from `sessions.spec.ts`) or re-use the pattern in `auth.spec.ts`.
4. New fixtures → add to the seed list in `global-setup.ts`. Label them deterministically; don't rely on row order.

### When something leaks

If a run crashes before teardown:

- Leftover rows stay marked `meta.e2e_test=true`.
- Next run's `sweepStaleRows` removes anything older than 60 min.
- To nuke on demand:

  ```sql
  delete from public.triage_sessions where meta->>'e2e_test' = 'true';
  ```
