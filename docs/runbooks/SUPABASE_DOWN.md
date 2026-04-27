# Runbook: Supabase Down / Unreachable

## Quick checklist (incident → green)

- [ ] Backend `/health` → check the `supabase` field
- [ ] Supabase status page (https://status.supabase.com)
- [ ] If provider-wide: comms on status page + #triaige-ops
- [ ] If our project only: Supabase dashboard → Project → Health
- [ ] Triage `/v1/triage/turn` keeps working (deterministic fallback);
      feedback + admin + send-summary degrade
- [ ] Decision: wait for provider vs. swap pooler URL vs.
      failover to backup project
- [ ] Watch `/health` recovery; rate-limit alerts may fire as
      in-memory buckets drift from Redis cache
- [ ] Post-incident ticket (see bottom)

## Symptoms

- **Backend `/health`** returns 503 with `supabase: unreachable`.
- Every triage turn `POST /v1/triage/turn` returns **5xx** because
  `session_repo.create_session` / `update_session` raise.
- Admin dashboard `/admin/sessions` list fails to load.
- Slack alert from the new 5xx-rate middleware fires (if wired).

## Severity

- **P1 — serving broken.** Unlike the LLM outage, Supabase is on
  the critical path: session IDs, event log, tenant catalog reads
  (for admin API) all require Postgres. Triage endpoint cannot
  complete a turn without writing to `triage_sessions`.

## Immediate mitigation (< 10 min)

1. Check https://status.supabase.com — is it a Supabase incident
   or our project specifically?
2. Backend logs — look for `RuntimeError: Missing SUPABASE_URL or
   SUPABASE_SERVICE_ROLE_KEY` (credential rotation accident) vs.
   network timeouts (provider incident).
3. If provider incident: **keep the frontend up** with a banner —
   the mobile app handles triage errors gracefully but the dashboard
   currently does not. Temporary static "maintenance in progress"
   page in front of `/admin/*` is the safest move.
4. If credential rotation: restore the correct env values,
   redeploy. Verify with `curl $BACKEND/health`.

## Data integrity

- Session writes queued up during the outage are **lost** — the
  client retries but the turn context is not persisted until
  Supabase is back. This is acceptable for pre-triage (not
  diagnostic) but operators should tell inbound calls "please
  re-describe once the session times out".
- Tenant catalog JSON files on disk are **unaffected** — those
  live on the backend container filesystem, not Supabase.
  Admin write path fails at the audit-row insert (defense-in-depth;
  the file write still succeeds — see `admin_tenants_api._write_audit_row`).

## Recovery

1. Once Supabase is back, verify health: `curl $BACKEND/health`
   should return `{"status": "ok", ...}`.
2. Run a single triage turn through the mobile app or curl to
   confirm `create_session` + `update_session` both succeed.
3. Check `triage_events` for the most recent session — new events
   should be appending.
4. Check `llm_calls` — post-recovery turns should log again.

## Escalation

- Outage > 1h: spin up a read-only Postgres replica from the most
  recent Supabase backup and point `SUPABASE_DB_URL` at it for
  admin dashboard only. Do NOT point the write path there — the
  replica is read-only and session inserts would fail silently.
- Outage > 4h: declare incident SEV-1, notify partner hospitals
  if multi-tenant is live — their admins will be unable to edit
  catalogs.

## Forensics

- Number of dropped turns during the window: count 5xx responses
  in the ingress log vs. count of successful `triage_sessions`
  INSERTs during the same window.
- Tenant catalog audit rows missing during the window (if any):
  cross-check filesystem `curated_conditions.*.json` mtimes
  against `tenant_catalog_audit` `created_at`.

## Prevention

- Add a pre-deploy smoke that pings `/health` and fails the
  deploy if Supabase is unreachable (deploy is safer than a
  half-broken new version taking over).
- Supabase has multiple connection strings (direct + pooler).
  Our `.env.example` documents both (`SUPABASE_DB_URL` +
  `SUPABASE_DB_POOLER_URL`). Confirm prod uses the pooler on
  IPv4-only networks.

## Post-incident checklist

- [ ] **Timeline**: detected, mitigated, green (UTC)
- [ ] **Root cause**: Supabase-side incident / our project /
      connection-pool exhaustion / schema migration gone wrong
- [ ] **Impact**: feedback rows lost? analytics dashboard gap?
      session-detail data missing for the window?
- [ ] **What went well** / **what didn't**: 3 bullets each
- [ ] **Action items**: pooler config audit, `/health` response
      improvement, connection-recovery test
- [ ] Link postmortem from the Slack alert thread
- [ ] Close the incident in ops tracker
