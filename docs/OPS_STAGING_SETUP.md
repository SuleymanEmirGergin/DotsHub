# Staging / E2E bring-up checklist

The repo ships a Playwright staging project that exercises the real
admin flow (magic-link auth, seeded sessions, status tiles) against a
live Supabase + deployed dashboard. This doc is the one-time setup
plus the recurring credential-rotation flow.

The localhost smoke (`.github/workflows/dashboard-tests.yml` → `test`
job) runs on every PR and doesn't need any of this. The staging job
(`e2e-staging`) runs only on `workflow_dispatch` with
`include_staging=true` or on the nightly schedule.

## One-time setup

### 1. Provision staging Supabase

Create a dedicated Supabase project for staging — **never point the
staging e2e at production.** The tests create + delete admin users,
seed + clean triage sessions, and generate magic links via the
Service Role key. Production data would be polluted or worse
deleted.

1. Supabase dashboard → New project → name `triaige-staging`.
2. Copy from **Settings → API**:
   - `Project URL` → `STAGING_SUPABASE_URL`
   - `anon` public key → `STAGING_SUPABASE_ANON_KEY`
   - `service_role` (secret) key → `STAGING_SUPABASE_SERVICE_ROLE_KEY`
3. Apply the schema:
   ```bash
   cd backend
   for f in sql/*.sql; do
     psql "$STAGING_SUPABASE_DB_URL" -f "$f"
   done
   ```
4. Create the E2E admin email. The test run auto-provisions it via
   `auth.admin.createUser`, so any valid-shaped address works:
   - `STAGING_TEST_ADMIN_EMAIL=e2e-admin@triaige.example`

### 2. Deploy staging dashboard (Vercel)

1. Vercel → Import GitHub repo → `triaige` — deploy the `main`
   branch.
2. **Settings → Environment Variables** (Preview + Production both):
   - `SUPABASE_URL` (same as `STAGING_SUPABASE_URL`)
   - `SUPABASE_SERVICE_ROLE_KEY` (same as above)
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `ADMIN_API_KEY` (any strong random string; write it down — the
     backend uses the same value)
3. Copy the deployed preview URL → `STAGING_BASE_URL`
   (e.g. `https://triaige-staging.vercel.app`).
4. **Optional**: enable Deployment Protection (SSO wall) and create a
   "Protection Bypass for Automation" secret. Copy it to
   `VERCEL_AUTOMATION_BYPASS_SECRET`. Tests attach it as an
   `x-vercel-protection-bypass` header.

### 3. Set GitHub repository secrets

In the GitHub repo → **Settings → Secrets and variables → Actions**,
add each of these. Leave any optional ones blank:

| Secret | Required | Purpose |
|---|---|---|
| `STAGING_BASE_URL` | ✅ | Vercel preview / staging URL |
| `STAGING_SUPABASE_URL` | ✅ | Supabase project URL |
| `STAGING_SUPABASE_ANON_KEY` | ✅ | Client-side (anon) key |
| `STAGING_SUPABASE_SERVICE_ROLE_KEY` | ✅ | Admin Service-Role key |
| `STAGING_TEST_ADMIN_EMAIL` | ✅ | E2E admin provisioning email |
| `VERCEL_AUTOMATION_BYPASS_SECRET` | optional | Bypass Vercel SSO wall |

### 4. Smoke-run the staging job

1. GitHub → Actions → **Dashboard tests** → Run workflow.
2. Set `include_staging=true` and run.
3. Expected: `test` passes (always does); `e2e-staging` job spins up
   Playwright, runs `auth.spec`, `sessions.spec`, `status.spec`, and
   finishes green in ~5 min. Artifacts (`playwright-report-staging`)
   attached on both success and failure.

If the job fails, read the artifact's error screenshots — the tests
dump cookie state + console/page errors on failure, so you can
usually diagnose without re-running locally.

## Scheduled nightly run

The workflow also runs on a daily cron (`0 6 * * *` UTC in
`.github/workflows/dashboard-tests.yml`). This catches:
- Staging Supabase drift (schema or RLS policy changed upstream)
- Vercel deployment-protection changes
- Expired bypass secrets

If the nightly red-light pings ops too often for stable reasons, tune
the cron or disable it; it's a drift-catcher not a blocking gate.

## Credential rotation

Quarterly or on any suspected compromise:

1. Generate new `STAGING_SUPABASE_SERVICE_ROLE_KEY` in Supabase
   dashboard.
2. Update the GitHub secret.
3. Update the Vercel env var.
4. **Don't** rotate the anon key unless you've also regenerated any
   long-lived client tokens — it invalidates in-flight browser
   sessions.
5. Trigger a manual staging run to confirm everything still connects.

For `VERCEL_AUTOMATION_BYPASS_SECRET`: rotate via Vercel dashboard →
Settings → Deployment Protection → regenerate. Update the GitHub
secret. Manual staging run to confirm.

## Teardown

If you're retiring staging:
1. Delete the Supabase project (backup first if you want the schema).
2. Revoke the Vercel project.
3. Clear all `STAGING_*` GitHub secrets.
4. Edit `.github/workflows/dashboard-tests.yml` and remove the
   `e2e-staging` job + cron schedule.

## Related docs

- `SECURITY.md` — security posture and incident response
- `docs/OPS_ROTATION.md` — secret rotation schedule
- `dashboard/e2e/README.md` — Playwright test authoring guide
