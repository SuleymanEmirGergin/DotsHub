# Security Policy

TriAIge is a medical pre-triage application that handles patient
symptoms, free-text health complaints, and session metadata subject to
Turkish KVKK (Kişisel Verileri Koruma Kanunu) and, where applicable,
GDPR obligations. This document describes the project's security
posture, vulnerability reporting process, and operator expectations.

## Reporting a vulnerability

Report suspected vulnerabilities to **security@triaige.example** (or
open a private security advisory on GitHub — not a public issue).

Include, at minimum:
- Affected component (backend / mobile / dashboard / infrastructure)
- Minimum reproduction steps
- Observed impact + proof-of-concept if non-invasive
- Your contact details and preferred disclosure timeline

Our commitments:
- **Acknowledge within 3 business days.**
- **Triage decision within 10 business days** (severity + owner).
- **Coordinated disclosure**: we'll agree on a public-disclosure
  timeline once a fix has been merged and deployed to all production
  tenants. Default embargo is 30 days after deployment.
- **Credit**: we're happy to credit reporters in the CHANGELOG and,
  where applicable, on a security-acknowledgements page. Opt-out
  respected.

Please do not run automated vulnerability scanners against production
hosts without prior written approval. Supply-chain reports (npm /
PyPI advisories) that affect our dependency tree are in scope even
if we didn't introduce the underlying bug.

## Supported versions

Only the `main` branch receives security fixes. We don't ship
long-lived feature branches; downstream users should track `main` or
a recent tag. Pinned release tags older than 90 days should be
considered unsupported and upgraded.

## Reporting scope

In-scope targets:
- Application code: `backend/`, `mobile/`, `dashboard/`
- Public API: `/v1/*` endpoints
- Configuration examples: `backend/.env.example`, mobile `app.json`
- CI / GitHub Actions workflows under `.github/workflows/`
- Runbooks under `docs/runbooks/`

Out of scope:
- Third-party infrastructure hosted by Supabase, Vercel, or Wiro.ai
  (report to the respective provider)
- Social engineering / physical attacks
- Denial-of-service via unauthenticated request volume (rate-limit
  gate already mitigates)
- Automated scan reports that don't include a reproduction

## Data handling posture

### Patient input (KVKK / GDPR)

- **Transport**: every `/v1/*` endpoint requires HTTPS; the
  `SecurityHeadersMiddleware` adds HSTS in production.
- **PII redaction**: `app/pii.py` is the canonical redactor.
  Applied before every third-party transmission (LLM provider,
  Sentry `before_send`, notifier webhooks) and before any row
  written to `synonym_suggestions`. New endpoints that transmit
  user input outside our infrastructure MUST route through it.
- **Right-to-delete**: `DELETE /v1/me/sessions/{session_id}`
  tombstones a triage session + hard-deletes derived rows
  (events, LLM calls, feedback). See `app/api/routes/data_rights.py`.
- **Retention**: `triage_sessions` tombstones are purged on a 90-day
  cron (external — currently manual). Content fields are wiped
  immediately at tombstone time.

### Authentication

- **Admin panel**: Supabase Auth magic-link, gated by an
  `admin_users` table row lookup in `requireAdmin()`. RLS policy in
  `backend/sql/20260419_admin_users_rls.sql`.
- **Backend admin API**: `X-Admin-Key` header compared to
  `ADMIN_API_KEY` env (rotate quarterly; see runbook).
- **Mobile client**: `x-device-id` header for rate-limit scoping
  only — not a trust anchor. All mutations are scoped to the
  session UUID passed in the body.

### Rate limiting

- `/v1/triage/turn` + `/v1/triage/feedback`: 20 req/min per device_id
  (or IP fallback) — tuned to protect Wiro API quota.
- `/v1/triage/send-summary` + `/v1/triage/export-summary`: 5 req/min
  per IP — tighter because email/PDF are expensive.
- `/v1/admin/*`: 60 req/min per IP.
- All buckets degrade to in-memory per-worker when Redis is
  unreachable (Session 3 fix — was "fail-open" before). A warn log
  fires once per bucket key; ops sees the split-brain in Loki.
- **Rejection-rate alerts**: `RATE_LIMIT_ALERT_*` env vars. Webhook
  fires when rolling-window rejection rate exceeds threshold.

### Secrets

- Never commit real secrets. `.env.example` files contain
  `change_me` placeholders; pre-commit hook (see
  `docs/OPS_ROTATION.md`) rejects `change_me` in non-example files.
- Rotate on a schedule:
  - `ADMIN_API_KEY`: quarterly
  - `SUPABASE_SERVICE_ROLE_KEY`: on admin offboarding or suspected
    leak
  - `WIRO_API_KEY` / `WIRO_API_SECRET`: on LLM-vendor auth-log
    anomaly
  - `SENTRY_DSN`: only rotate on project-move or suspected scraper

### Dependency posture

- Backend: `pip-audit` weekly (GitHub Action `dependency-audit.yml`,
  see `docs/runbooks/BAD_TENANT_CATALOG.md` for the response).
- Mobile: `npm audit --omit=dev` in CI (blocks on critical).
- Dashboard: `pnpm audit --prod` in CI (blocks on critical).

## Incident response

The three runbooks in `docs/runbooks/` document operator procedures
for the most likely failure modes:
- `LLM_PROVIDER_DOWN.md` — Wiro outage
- `SUPABASE_DOWN.md` — DB unreachable
- `BAD_TENANT_CATALOG.md` — curated-catalog rollback

Alerting paths:
- HTTP 5xx spike → webhook (`HTTP_5XX_ALERT_*` env)
- LLM success rate drop → webhook (`LLM_HEALTH_ALERT_*` env)
- Rate-limit rejection spike → webhook (`RATE_LIMIT_ALERT_*` env)
- Unhandled exceptions → Sentry (set `SENTRY_DSN` to activate)

For a security incident specifically, follow
`docs/runbooks/SECURITY_INCIDENT.md` (contains contact matrix,
disclosure template, PII-breach reporting steps per KVKK Article 12).

## Deploy-time checklist

Before deploying a new backend or dashboard version:
1. CI: all blocking jobs green (`golden-flow-regression`,
   `safety-critical-coverage`, `docker-build`, `test`, `jest`).
2. Dependency audit: no new critical CVEs.
3. Secrets: verify `.env` does not contain any `change_me`.
4. Migrations: `backend/sql/*.sql` applied in timestamp order.
5. Health endpoints reachable:
   - Backend: `GET /health` returns 200 with `supabase: ok`.
   - Dashboard: `GET /admin/status` renders all tiles green.
6. Rate-limit env: `REDIS_URL` set on multi-instance deploys.
7. Version gate: confirm `MIN_CLIENT_VERSION` matches the lowest
   acceptable mobile build currently in stores.

See `docs/OPS_STAGING_SETUP.md` for the first-deploy staging bring-up
and `docs/OPS_ROTATION.md` for the quarterly secret rotation flow.

## Credits

This security policy and the accompanying runbooks were written with
the assistance of Claude (Anthropic) during the Session 4 operational
hardening sprint.
