# Secret rotation schedule

This doc is the recurring cadence for rotating every
externally-issued credential the system uses. Following it is cheap
insurance; skipping it is how a leak-in-log becomes a breach later.

Rotation always follows the same shape: **generate new → update in
env → verify with canary request → revoke old**. Don't do them in
parallel; revoking before verify is how you accidentally take prod
down.

## Schedule

| Credential | Cadence | Scope | Impact of bad rotation |
|---|---|---|---|
| `ADMIN_API_KEY` | Quarterly | Backend `/v1/admin/*` | Dashboard loses backend calls |
| `SUPABASE_SERVICE_ROLE_KEY` | Quarterly | Backend + dashboard server | All Supabase writes stop |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Only on suspected leak | Dashboard client | In-flight browser sessions fail |
| `WIRO_API_KEY` + `WIRO_API_SECRET` | Quarterly | LLM NLU | LLM extraction falls back to deterministic |
| `SENTRY_DSN` | Only on project move | Error aggregation | Events stop flowing to Sentry |
| `WEBHOOK_SLACK_URL` | Annually | Ops alerts | No pager alerts |
| `WEBHOOK_DISCORD_URL` | Annually | Ops alerts | No pager alerts |
| `STAGING_*` (all) | Quarterly | Playwright staging e2e | Nightly e2e fails |
| `VERCEL_AUTOMATION_BYPASS_SECRET` | Annually | Playwright staging | Staging e2e gets SSO wall |
| OAuth client secrets (if added) | Quarterly | Whoever consumes | Downstream auth breaks |

## Quarterly rotation playbook

Block out a 2-hour window. Announce in #dotshub-ops 24 hours prior.

### 1. `ADMIN_API_KEY`

```bash
# 1. Generate a new key
NEW_KEY=$(openssl rand -hex 24)
echo "ADMIN_API_KEY=$NEW_KEY"  # write it down

# 2. Update backend env (Railway / Fly / wherever)
#    AND dashboard env (Vercel — server-side envs)

# 3. Canary: hit an admin endpoint with the NEW key
curl -H "x-admin-key: $NEW_KEY" https://api.dotshub.example/v1/admin/sessions | head -c 200

# 4. Revoke old key by deleting from envs + restarting workers
```

### 2. `SUPABASE_SERVICE_ROLE_KEY`

```
Supabase dashboard → Settings → API → Service-role key → Regenerate
```

1. Copy the new key **before clicking regenerate** (Supabase shows
   it only once).
2. Update backend env, dashboard env, GitHub secrets
   (`STAGING_SUPABASE_SERVICE_ROLE_KEY` too).
3. Canary: `GET /health` on backend → `supabase: ok`.
4. Canary: dashboard admin login → `/admin/sessions` loads.
5. Old key is auto-revoked by Supabase on regenerate — no extra
   step needed.

### 3. Wiro

```
Wiro dashboard → API Keys → Create new → Revoke old after 24h
```

1. Update `WIRO_API_KEY` and `WIRO_API_SECRET` in backend env.
2. Canary: trigger a triage turn that has `LLM_NLU_ENABLED=true` and
   check Wiro admin → API logs for the new key's auth.
3. Keep old key for 24h as a rollback window; revoke after.

### 4. `STAGING_*` secrets

See `docs/OPS_STAGING_SETUP.md` §"Credential rotation" — same flow
as initial setup, just the rotation half.

### 5. Webhook URLs (Slack / Discord)

```
Slack: Apps → Incoming Webhooks → revoke + create new
Discord: Server Settings → Integrations → Webhooks → create new
```

1. Update `WEBHOOK_SLACK_URL` / `WEBHOOK_DISCORD_URL` in backend env.
2. Canary: trigger a test alert:
   ```bash
   curl -X POST https://api.dotshub.example/v1/admin/test-webhook \
     -H "x-admin-key: $ADMIN_API_KEY"
   ```
3. Confirm message lands in the right channel.

## On-demand rotation (suspected leak)

Trigger the full rotation for the affected credential only. Don't
wait for the scheduled cadence:

- Leaked in a public commit → revoke immediately, rotate, audit
  access logs for the leak window (see
  `docs/runbooks/SECURITY_INCIDENT.md`).
- Employee offboarding → rotate anything they had access to
  (`ADMIN_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY` at minimum).
- Auth-log anomaly → rotate and audit.

## Automation hooks

`gitleaks` runs on every PR in CI and blocks pushes that contain
obvious secret patterns. It's a safety net, not a substitute —
real leak detection still requires log review.

`pre-commit` hook (when present) rejects commits that contain
`change_me` in any non-example file. If you need the literal text
in a test fixture, use `change_me_intentional_test_literal` or
add the file to the hook's allow-list.

## Audit log

Keep a `rotations.log` file (private, not in this repo) with:
- Date, time
- Credential rotated
- Who performed
- Reason (scheduled / leak / offboarding)
- Verification canary result

Annual security review pulls this log to confirm cadence is
actually being followed.
