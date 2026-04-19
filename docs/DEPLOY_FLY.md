# Backend Production Deploy — Fly.io

This doc is the end-to-end recipe for getting the Dotshub FastAPI
backend live on Fly.io, region `ams`, with Upstash Redis for multi-
instance rate-limit, behind a Fly-managed HTTPS edge.

**Audience:** the repo owner running the first deploy. If you've
already deployed once, the only things you'll revisit here are the
secrets list (§3) and the verify commands (§6).

## Architecture after deploy

```
 Internet
    │
    ▼  HTTPS (Fly edge — TLS terminated here)
 ┌──────────────────────────────────────────────────────┐
 │  Fly machine (ams, shared-cpu-1x, 512 MB)            │
 │  ┌──────────────────────────┐                        │
 │  │ app process              │                        │
 │  │   uvicorn :8000          │◀── /metrics (A3 agent) │
 │  │   + /health              │                        │
 │  └──────┬───────────────────┘                        │
 │         │                                            │
 │         ▼                                            │
 │   Upstash Redis ─── rate-limit bucket                │
 └────────┬─────────────────────────────────────────────┘
          │
          ▼
     Supabase (postgres + auth) — managed, outside Fly
```

After Phase A3 a second Fly process (`agent`) runs next to `app`,
scraping `127.0.0.1:8000/metrics` and pushing to Grafana Cloud.

## 1. Prerequisites

- GitHub repo access (you have it)
- A Fly.io account (see §2)
- `flyctl` installed locally
- A credit card on file with Fly.io — hobby-tier apps generally run
  $0, but Fly requires a card to prevent abuse
- Your Supabase project's **Service Role Key** and URL (from the
  Supabase dashboard → Project Settings → API)
- Your Wiro API key + secret (already in `backend/.env`)

## 2. Install flyctl + auth (first time only)

### Windows (PowerShell)
```powershell
iwr https://fly.io/install.ps1 -useb | iex
# Close + reopen PowerShell to pick up the PATH change
flyctl version
# → flyctl v0.3.xxx ...
```

### macOS / Linux
```bash
curl -L https://fly.io/install.sh | sh
flyctl version
```

### Sign up + log in
```bash
flyctl auth signup      # only if you don't have an account yet
flyctl auth login       # opens browser, authorises the CLI
flyctl auth whoami      # → your email
```

Browser will redirect you to fill billing details on first sign-up.

## 3. Required + optional secrets

Copy values from your `backend/.env` (or Supabase dashboard). **Never
commit these anywhere** — `flyctl secrets set` encrypts them at rest
and injects into the machine at runtime.

### Required (deploy will fail without these)

| Secret | Source | Notes |
|--------|--------|-------|
| `SUPABASE_URL` | Supabase → Project Settings → API | `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → service_role | The "secret" one, **not** anon. ~200 char JWT |
| `WIRO_API_KEY` | `backend/.env` | For LLM NLU |
| `WIRO_API_SECRET` | `backend/.env` | HMAC signing |
| `ADMIN_API_KEY` | Generate now (see box) | Admin stats / export auth |
| `CORS_ORIGINS` | See §5 | JSON array string |

> Generate `ADMIN_API_KEY` with one of:
> ```powershell
> # Windows (PowerShell 5+)
> -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | % {[char]$_})
> ```
> ```bash
> # macOS/Linux
> openssl rand -hex 24
> ```

### Optional (add as needed — deploy works without them)

| Secret | Purpose | Skip if… |
|--------|---------|----------|
| `SUPABASE_DB_URL` | Direct Postgres | You only hit Supabase via REST |
| `SUPABASE_DB_POOLER_URL` | IPv4 pool | Your network is IPv6-OK |
| `RESEND_API_KEY` | Email digest | You don't need email |
| `SENTRY_DSN` | Error aggregation | You're OK without errors shipped out |
| `GRAFANA_CLOUD_PROM_URL` + `GRAFANA_CLOUD_PROM_USER` + `GRAFANA_CLOUD_PROM_TOKEN` | Observability (Phase A3) | Phase A3 will add these |

### Auto-injected by Fly.io (do not set manually)

| Secret | Set by |
|--------|--------|
| `REDIS_URL` | `flyctl redis create` / Upstash extension |

## 4. First deploy — the 6 commands

Run these in order from the **repo root** (not `backend/`). Each step
is safe to re-run if it fails mid-way — operations are idempotent.

```bash
# One: create the app (Fly reads fly.toml; if app name collides with
# someone else's, rename `app` in fly.toml and retry).
flyctl apps create dotshub-backend --org personal

# Two: provision Upstash Redis (free-tier — 10K cmd/day, 256 MB).
# This attaches REDIS_URL as a secret on `dotshub-backend`.
flyctl redis create \
  --name dotshub-redis \
  --region ams \
  --plan free \
  --no-replicas

# Three: set secrets (paste actual values in place of <…>). Stagger
# long secrets into multiple invocations if your shell complains
# about line length.
flyctl secrets set \
  SUPABASE_URL="<paste>" \
  SUPABASE_SERVICE_ROLE_KEY="<paste>" \
  WIRO_API_KEY="<paste>" \
  WIRO_API_SECRET="<paste>" \
  ADMIN_API_KEY="<paste>" \
  CORS_ORIGINS='["http://localhost:3000","https://dotshub.vercel.app"]'
  # ↑ Comma-separated JSON. Update the Vercel URL in §5 once you know it.

# Four: first build + deploy. ~3-5 minutes.
flyctl deploy

# Five: wait for the machine to come up, then confirm.
flyctl status
# → look for "State: started" + "Health: passing"

# Six: hit /health from your laptop.
curl https://dotshub-backend.fly.dev/health
# → {"status":"ok","supabase":"reachable",...}
```

## 5. CORS origins — update once frontend URLs are known

The minimal `CORS_ORIGINS` for the first deploy is `localhost:3000` +
your Vercel-deployed dashboard URL. After Phase A2 (pointing mobile +
dashboard at the prod backend), refresh the list:

```bash
flyctl secrets set \
  CORS_ORIGINS='["http://localhost:3000","https://<your-dashboard>.vercel.app","https://dashboard.dotshub.com"]'
# Fly will restart the machine with the new env.
```

Add every origin the backend needs to accept requests from — no
wildcard. Wildcards + credentials = browser refuses the response.

## 6. Verification

Ran all three:

```bash
# 1) Fly-side health — shows the machine state, recent restarts, CPU/mem.
flyctl status
flyctl logs --no-tail        # last ~200 log lines
flyctl checks list           # green = /health passing

# 2) Backend-side smoke — hit the public URL.
curl -sS https://dotshub-backend.fly.dev/health | jq
curl -sS https://dotshub-backend.fly.dev/v1/config/features | jq
# → client-version payload

# 3) Metrics endpoint — required for Phase A3.
curl -sS https://dotshub-backend.fly.dev/metrics | head -30
# → HELP/TYPE lines, Prometheus exposition format
```

If any of these fail, `flyctl logs --no-tail` is usually enough to
diagnose. Common first-deploy failures:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `supabase connection refused` | `SUPABASE_URL` wrong or unset | `flyctl secrets list` to confirm; re-set if missing |
| `CORS blocked` in browser | Vercel URL not in `CORS_ORIGINS` | See §5 |
| Machine restarts every 30s | `/health` failing (Supabase) | Log shows which check; usually a secret issue |
| Build fails at `pip install` | Transient network | `flyctl deploy` again (idempotent) |
| `redis connection timeout` | Upstash not ready yet | Wait 60s after `redis create`, redeploy |

## 7. Phase A2 — redirect clients to prod backend

After the Fly URL is confirmed live, update the client configs:

**Dashboard (`dashboard/.env.production`):**
```
NEXT_PUBLIC_API_BASE=https://dotshub-backend.fly.dev
```
Then push; Vercel picks up the new env on the next deploy.

**Mobile (`mobile/.env`):**
```
API_BASE=https://dotshub-backend.fly.dev
```
Rebuild your Expo app (`npx expo start --clear`) or bump the EAS
binary.

## 8. Phase A3 — agent sidecar + live observability

Covered in `docs/OBSERVABILITY.md` §"Fly.io sidecar". Short version:
add a second process `agent` to `fly.toml`, `flyctl secrets set` the
Grafana Cloud + Sentry credentials, `flyctl deploy`. The agent
scrapes `127.0.0.1:8000/metrics` and pushes to Grafana Cloud.

## 9. Rollback

Fly keeps previous deploys for instant rollback:

```bash
flyctl releases                   # list last N deploys, most recent first
flyctl releases rollback <id>     # promote an older release
```

Schema changes live in Supabase, not Fly — rolling back the Fly app
does NOT touch the DB. If a deploy involved a schema migration,
revert the migration separately.

## 10. Scale up (when idle-cold-start becomes a real problem)

```bash
flyctl scale count 1 --min 1      # always-on single machine
flyctl scale count 2              # + a second machine in the same region
flyctl scale vm shared-cpu-2x --memory 1024   # bump the size
```

Upstash Redis on a paid plan lifts the 10K cmd/day cap. Until rate-
limit traffic approaches that, the free tier is fine.

---

## Operator-side checklist (tear-off copy)

- [ ] `flyctl` installed + `flyctl auth whoami` shows my email
- [ ] Billing card on file at Fly.io
- [ ] `ADMIN_API_KEY` generated + saved somewhere safe
- [ ] `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` copied from Supabase dashboard
- [ ] `WIRO_API_KEY` + `WIRO_API_SECRET` copied from `backend/.env`
- [ ] Dashboard Vercel URL known (for `CORS_ORIGINS`)
- [ ] `flyctl apps create dotshub-backend --org personal` done
- [ ] `flyctl redis create --plan free` done
- [ ] `flyctl secrets set …` done (at least the 6 required)
- [ ] `flyctl deploy` green
- [ ] `curl /health` returns ok
- [ ] Phase A2: clients pointed at prod URL
- [ ] Phase A3: agent sidecar scraping + pushing
