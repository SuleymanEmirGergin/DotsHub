# Disaster Recovery Runbook — TriAIge Backend

**Owner:** emirgergin21@gmail.com (TriAIge founder, current on-call).
**Audience:** on-call engineer when prod is on fire.
**Companion docs:** `docs/RUNBOOK.md` (operational alerts),
`docs/runbooks/SUPABASE_DOWN.md`, `docs/runbooks/LLM_PROVIDER_DOWN.md`,
`docs/runbooks/SECURITY_INCIDENT.md`.

This document is read at 03:00 with adrenaline. It is structured for
decision-making, not for explanation. For each scenario:

- **Detection** — which alert fires; how the on-call sees it first.
- **Severity** — P0/P1/P2 with criteria.
- **Immediate actions (first 5 minutes).**
- **Recovery (next 30 minutes).**
- **Communication.**
- **Post-mortem trigger.**
- **Verification.**

Severity convention:
- **P0** — patients cannot complete a triage turn at all; or PII
  has been exposed. Wake everyone. Public status update within 30 min.
- **P1** — degraded but serving; partial outage. On-call only.
- **P2** — observability degraded; users do not see impact.

---

## 1. Supabase outage

**What the user sees today.** `_handle_turn_supabase` in
`backend/app/api/routes/triage.py` calls `create_session` /
`update_session` against Supabase. On a Supabase failure, the call
raises and the outer handler returns an `ERROR` envelope with code
`TURN_FAILED` and `retryable: true`. The mobile app retries; if
Supabase is still down the user gets a generic error toast and the
session never persists.

`/health` returns the supabase reachability status as a sub-field
(`"supabase":"ok"|"unreachable"`).

There is a partial fallback path for the case where the Supabase
schema is *missing* (PGRST205 / 42P01) — `_is_missing_supabase_schema_error`
catches that specific error class and falls back to the legacy
in-memory orchestrator. **This fallback does NOT trigger on a generic
Supabase outage** — only on schema-not-found. A network outage to
Supabase REST currently has no graceful fallback. **Verify this** by
re-reading `triage.py:358-369` if behavior has changed.

| Field | Value |
|-------|-------|
| **Detection** | Grafana alert `BackendHighErrorRate` (5xx > 2% × 5m); `/health` returns `"supabase":"unreachable"`; Sentry burst of `httpx.HTTPStatusError`. |
| **Severity** | **P1** — pre-triage cannot complete turns. **P0** if Supabase Auth is also down (admin dashboard locked). |
| **First 5 min** | 1. `flyctl logs --app triaige-backend --no-tail`. 2. `curl https://triaige-backend.fly.dev/health`. 3. https://status.supabase.com — provider incident or our project? 4. If credential issue: `flyctl secrets list` → look for missing/wrong `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`. |
| **Recovery (30 min)** | Provider incident: wait + post status. Our project: regenerate service-role key in Supabase dashboard, `flyctl secrets set`, redeploy. If outage > 30 min, push a maintenance banner via mobile feature flag (TODO: this flag does not currently exist — track as resilience improvement). |
| **Comms** | Internal: timeline log in #sec-incident or a temp Slack thread. External: status page (TODO — `status.triaige.com` not yet provisioned), in-app banner (TODO — feature flag missing). |
| **Post-mortem** | Required if outage > 30 min OR > 5% of daily session attempts hit ERROR envelope. |
| **Verification** | `/health` returns `"supabase":"ok"`; one synthetic POST `/v1/triage/turn` with a fixture body returns a `QUESTION` envelope; Grafana 5xx rate falls below 1% for 10 min sustained. |

**Recommended additions (resilience debt):**
- Cached fallback for read paths (history endpoint already returns
  `{"items": []}` on no-supabase; extend pattern to admin reads).
- Degraded read-only mode for ongoing sessions: cache the last
  envelope per session in Redis (existing Upstash) so a one-off
  Supabase blip on turn-2 doesn't lose turn-1 state.
- Mobile-side maintenance banner driven by a single feature-flag
  endpoint that does not depend on Supabase to evaluate.

See also: `docs/runbooks/SUPABASE_DOWN.md`, `docs/RUNBOOK.md` Flow C.

---

## 2. Fly.io app crash / restart loop

The most common DR scenario in practice — a deploy lands and the
machine crashloops. The Fly deploy workflow
(`.github/workflows/fly-deploy.yml`) has a `Verify health` step that
polls `/health` for 60 seconds after deploy and fails the workflow
on no-200; that surfaces some crashloops as a red CI run, but not
all (e.g., a deploy that succeeds, then crashes 10 minutes later
under traffic).

| Field | Value |
|-------|-------|
| **Detection** | Grafana alert `BackendScrapeDown` (`up == 0` × 2m); Fly machine state `stopped` from `flyctl status`; auto-restart counter increments. |
| **Severity** | **P0** — backend serving zero requests. |
| **First 5 min** | 1. `flyctl status --app triaige-backend` — confirm machine state. 2. `flyctl logs --app triaige-backend --no-tail` — read the last traceback at the bottom. 3. **Decision tree:** recent deploy in last 30 min → rollback (skip to recovery). Older or unclear → proceed to step 4. 4. Identify exception class: `JSONDecodeError` on a secret → secret format issue; `ModuleNotFoundError` → missing dep, requires deploy; `httpx.ConnectError` to Supabase → see scenario 1; `redis.ConnectionError` → graceful (in-memory fallback exists per `app/rate_limit.py`). |
| **Recovery (30 min)** | **Rollback procedure:** `flyctl releases --app triaige-backend` shows the recent deploy list with green/red status. `flyctl releases rollback <release-id> --app triaige-backend` promotes a previous release. The fly-deploy workflow does NOT automate rollback — this is intentional, see the workflow comments at top. **Caveat:** code rolls back, Supabase schema does NOT. If the bad deploy ran a SQL migration, manually revert the migration first via Supabase SQL Editor. **Last-resort:** `flyctl machines destroy <id> --app triaige-backend --force && flyctl deploy` (Flow I in `docs/RUNBOOK.md`). |
| **Comms** | Internal-only unless > 5 min downtime, then post incident channel timeline. |
| **Post-mortem** | Required for any rollback. Capture: which commit, why CI didn't catch it, follow-up gates needed. |
| **Verification** | `flyctl status` shows `state=started` AND `health=passing`; `curl /health` returns `200`; Grafana 5xx rate at baseline. |

**Existing references:**
- `docs/RUNBOOK.md` Flow A — Backend Crash Loop (matching content).
- `docs/DEPLOY_FLY.md` §9 — Rollback (`flyctl releases rollback`).
- `.github/workflows/fly-deploy.yml` — deploy gate + health verify.

---

## 3. Sentry outage

Sentry is the error-aggregation surface. If Sentry can't ingest, we
lose visibility into runtime errors but the app keeps running.

**Failure mode (verified).** `backend/app/observability/sentry_init.py`
imports `sentry_sdk` lazily and treats blank `SENTRY_DSN` as a no-op.
The `init_sentry()` function returns `False` on any import or
configuration failure and the rest of the app proceeds unaffected.
**TriAIge fails OPEN on Sentry — confirmed.** No request path blocks
on Sentry availability; Sentry's own SDK swallows transport errors
internally.

| Field | Value |
|-------|-------|
| **Detection** | Sentry's status page (https://status.sentry.io) signals "Event Ingest" degraded. Internally, no specific alert today — Sentry being down is invisible from our metrics. |
| **Severity** | **P2** — observability degraded; users see nothing. |
| **First 5 min** | 1. Check https://status.sentry.io. 2. Confirm app health: `curl /health`, `flyctl status`. 3. Pin a tab on Grafana for the duration — error visibility falls back to logs + metrics. |
| **Recovery (30 min)** | Wait. Sentry outages are rare and short. If extended (> 4 hours): export `flyctl logs` to a local file every hour as evidence-preservation; tail Grafana 5xx metric instead of Sentry issue list. |
| **Comms** | None unless we lose a separate prod incident during the Sentry blackout. |
| **Post-mortem** | Only if a real incident was missed because Sentry was the only alarm path. Use this as a forcing function to add a parallel alarm in Grafana. |
| **Verification** | Test event from Sentry dashboard arrives within 60s. |

**Resilience addition:** the `sentry-smoke.yml` GitHub workflow runs a
periodic smoke that posts a controlled event and asserts arrival. If
Sentry is down, this workflow goes red, which is itself an alarm.

---

## 4. OpenAI / LLM provider outage

The LLM (Wiro is the current provider per `flyctl secrets`; see
`docs/runbooks/LLM_PROVIDER_DOWN.md`) provides NLU enrichment to
canonical extraction. **The triage flow does not block on the LLM** —
`backend/app/services/llm_nlu.py` falls back to deterministic
extraction (`backend/app/canonical_extract.py`) on every LLM failure.

**Verified failover path.** `LLM_NLU_ENABLED=false` is the kill switch.
With it set, every turn computes `nlu_source = "deterministic"` and
no Wiro calls are made. The triage envelope is unaffected in
structure; only canonical-extract richness drops marginally. The
metric `llm_nlu_calls_total{success="false"}` fires the
`LLMNluRateLimitSaturated` alert when failures cluster.

| Field | Value |
|-------|-------|
| **Detection** | Grafana alert `LLMNluRateLimitSaturated`; Slack/Discord webhook from `send_llm_health_alert()` ("LLM NLU başarı oranı düştü: %X"); admin analytics card "LLM NLU Health" red-bordered. |
| **Severity** | **P2** — degraded but serving. **P1** only if real_corpus pass rate visibly regresses (rare). |
| **First 5 min** | 1. Wiro status (https://wiro.ai or provider dashboard). 2. `flyctl secrets set --app triaige-backend LLM_NLU_ENABLED=false`. The deploy completes in ~30s; new turns immediately route to deterministic NLU. 3. Verify in `/admin/sessions/[id]` LLM-calls table that no new LLM rows appear after the toggle. |
| **Recovery (30 min)** | Auth regression: rotate Wiro key per `docs/OPS_ROTATION.md`. Quota exhausted: bump plan or wait for quota reset. Provider incident: wait + monitor. Re-enable: `flyctl secrets set LLM_NLU_ENABLED=true` once provider returns. |
| **Comms** | Internal only (P2). |
| **Post-mortem** | Required if `LLM_NLU_ENABLED=false` lasts > 24 hours OR if real_corpus pass rate dropped > 3% during the window. |
| **Verification** | A fresh turn produces `nlu_source = "wiro"` (or current provider) again; `llm_nlu_calls_total{success="true"}` rate recovers to > 80%. |

**Cross-reference:** `docs/runbooks/LLM_PROVIDER_DOWN.md` (full
recovery checklist), `docs/RUNBOOK.md` Flow F.

---

## 5. DDoS / abusive traffic burst

Layered defenses today, in the order traffic hits them:

1. **Fly.io edge** — handles TLS termination, basic L4 protection.
   Not configurable from our side beyond what Fly provides.
2. **No Cloudflare in front today** — staging and prod both face the
   internet via Fly's anycast network directly. Cloudflare in front
   is tracked as a future improvement (referenced in
   `docs/RUNBOOK.md` Flow E).
3. **Per-IP rate limit** — `backend/app/rate_limit.py` enforces
   `RATE_LIMIT_MAX_REQ` (default 20 / 60s) per source IP, with a
   Redis-backed bucket for multi-instance consistency and an
   in-memory fallback on Redis errors. The denied path returns 429
   and increments `rate_limit_hits_total{outcome="denied"}`.
4. **Admin / send_summary buckets** — separate stricter limits.

| Field | Value |
|-------|-------|
| **Detection** | Grafana alert `RateLimitDeniedRateHigh` (>5% × 15m); CPU saturation on Fly machine; sudden spike in 429 rate; Sentry burst of low-quality requests. |
| **Severity** | **P1** — legitimate users get 429s alongside attackers. **P0** if attack is sized to exhaust Fly machine CPU and `/health` starts failing. |
| **First 5 min** | 1. Identify attacker: which IP / IPs. Grafana → top denied IPs (need to add this query if not already in dashboard). 2. **Panic switch (current capability):** `flyctl secrets set --app triaige-backend RATE_LIMIT_MAX_REQ=5 RATE_LIMIT_WINDOW_SEC=60` — tighten the cap. Restart picks it up. 3. Tenant-level lock: admin API has tenant management endpoints in `backend/app/admin_tenants_api.py`; manual toggle of a tenant's `enabled` field via Supabase SQL Editor is the fastest panic-lock today (TODO: expose as admin API). |
| **Recovery (30 min)** | Sustained attack from a small IP set: write the IPs to a deny-list (TODO: this list does not exist — `docs/RUNBOOK.md` Flow E acknowledges the gap). Long-term mitigation: front Fly with Cloudflare and configure WAF rules. Bot-style scraping: tighten validation on `POST /v1/triage/turn` body shape; reject messages with no extractable Turkish content (the canonical extractor returns empty list — log + 429 those over a threshold). |
| **Comms** | Internal-only unless legitimate users are affected for > 30 min. |
| **Post-mortem** | Required for any P0; required for any P1 longer than 1 hour. Output: written follow-up to add Cloudflare. |
| **Verification** | 429 rate falls back to baseline; CPU on Fly machine returns to < 50%; legitimate test session completes a 4-turn flow without retry. |

---

## 6. Data breach / PII leak

KVKK requires notification to the data protection authority within
**72 hours** of awareness, plus notification to affected data subjects
"without undue delay" when the breach is likely to result in high risk
to their rights (Article 12 of Law 6698, aligned with GDPR Article
33-34 in spirit but with TR-specific timing).

| Field | Value |
|-------|-------|
| **Detection** | Sentry / log alert on `PII leak detected` heuristic (TODO — this heuristic does not yet exist); user report; security researcher disclosure; suspicious DB query in Supabase audit log. |
| **Severity** | **P0** unconditionally. |
| **First 5 min** | 1. **Do NOT delete logs or rotate keys yet** (preserve evidence — see `docs/runbooks/SECURITY_INCIDENT.md`). 2. Open private incident channel. 3. Stop the bleeding: block the abusing IP / disable the leaked credential / revoke the access token. 4. Snapshot the logs + Sentry events to a secure bucket. 5. Notify legal counsel + KVKK DPO (placeholders today; pre-fill these contacts before pilot launch). |
| **Recovery (within 72h)** | a. Forensics: scope the breach — which records, when, how. b. Patch the vulnerability. c. Notify KVKK Kurumu within 72 hours via the official channel (https://www.kvkk.gov.tr/). d. Notify affected users with the legally-required content (nature of breach, likely consequences, mitigation). e. File the post-mortem. |
| **Comms** | Internal: incident channel + legal counsel. External (legal mandate): KVKK Kurumu within 72h; affected users via in-app + email; public statement on website if breach is large. **Pre-draft the notification template now**, before an incident — see template below. |
| **Post-mortem** | Required, public-facing, signed by founder. Industry expectation: within 14 days of resolution. |
| **Verification** | Vulnerability patched + verified; no recurrence in monitoring window; KVKK ack received; affected users notified. |

**Notification template (to pre-draft, save in `docs/templates/`):**

```
Konu: TriAIge — Veri Güvenliği Bildirimi (KVKK Madde 12)

Sayın <Kullanıcı>,

<Tarih>'te TriAIge sistemlerinde tespit ettiğimiz bir güvenlik
olayını sizinle paylaşmak istiyoruz. <Olayın doğası — ne, ne zaman,
nasıl tespit edildi>.

Bu olayda etkilenen veri kategorileri: <kategoriler>.
Olası sonuçlar: <olası riskler>.
Aldığımız önlemler: <patch + mitigation>.

Sizden talep ettiğimiz aksiyon: <varsa>.

Yetkili veri koruma kurumu (KVKK Kurumu) <Tarih>'te bilgilendirilmiştir.

Sorularınız için: privacy@triaige.com
```

**Cross-reference:** `docs/runbooks/SECURITY_INCIDENT.md`,
`docs/PRIVACY_AND_SECURITY.md`, `docs/templates/KVKK_DPA_TEMPLATE.md`.

---

## 7. Database restore from Supabase backup

Supabase auto-backups are available on Pro tier and above. Free tier
has no backups — verify which tier the prod project is on **before**
needing the backup. Default retention on Pro is 7 days of daily
backups + Point-in-Time Recovery (PITR) within the retention window.

| Field | Value |
|-------|-------|
| **Detection** | Trigger is a manual decision after data corruption / accidental delete is confirmed. NOT automated. |
| **Severity** | **P0** if data loss affects > 1 day of sessions. **P1** if isolated to a small range. |
| **First 5 min** | 1. **Stop writes** — set `LLM_NLU_ENABLED=false` is not enough; we need to put the backend in maintenance mode. Today's coarse fix: `flyctl scale count 0 --app triaige-backend`. This stops serving entirely; restart with `flyctl scale count 1` after restore. 2. Determine target restore point — last known-good timestamp. |
| **Recovery (30 min - 2 hours depending on DB size)** | Supabase dashboard → Project → Database → Backups. Two paths: (a) **Full backup restore** to a NEW project, then swap `SUPABASE_URL` secret on Fly. Cleaner; preserves the bad project for forensics. (b) **PITR in-place** — restores the existing project to a point in time. Faster but destroys post-incident state. Path (a) is preferred unless time-critical. Verify schema migrations match between backup and code. Run `backend/sql/*.sql` if any migrations landed after backup. |
| **Comms** | Internal during restore. External notification if user data is affected (see scenario 6). |
| **Post-mortem** | Always. Restore drills are rare; the actual run reveals what was missing. |
| **Verification** | `select count(*) from triage_sessions where created_at > '<restore-point>'` matches expected pre-incident count; one synthetic triage flow E2E succeeds; admin dashboard renders without errors. |

**Verify before pilot:** is the prod Supabase project on Pro tier with
backups enabled? Default Free tier has no backups. **Mark "verify"**
until checked in the Supabase dashboard.

**Reference:** Supabase docs at https://supabase.com/docs/guides/platform/backups.

---

## 8. Domain / DNS / certificate failure

Domain `triaige.com` (and any subdomains: `dashboard.triaige.com`,
future `status.triaige.com`) — registrar account ownership and
expiry monitoring.

| Field | Value |
|-------|-------|
| **Detection** | TLS expiry monitoring service (e.g., letsmonitor, BetterUptime) — TODO, not yet wired. Browser certificate warnings reported by users. DNS lookup failures from external monitor (UptimeRobot — TODO). |
| **Severity** | **P0** — domain unreachable means total outage from a user perspective. |
| **First 5 min** | 1. Confirm: `dig triaige.com`, `curl https://triaige-backend.fly.dev/health` (Fly URL bypasses our domain). If Fly URL works but custom domain doesn't → DNS / cert issue. 2. Check registrar account (TODO — record the registrar name + login owner here, e.g., Namecheap / GoDaddy / Porkbun). 3. Check certificate: `openssl s_client -connect triaige.com:443 < /dev/null | openssl x509 -dates -noout`. |
| **Recovery (30 min)** | DNS hijack: emergency-contact registrar support, lock account, restore records from a known backup. Cert expiry: Fly auto-renews Let's Encrypt certs for app-level certs; for custom domain certs, re-issue via `flyctl certs add`. DNS misconfiguration: revert to last known-good record. |
| **Comms** | External — users will not be able to reach the app. Tweet from a brand account, mobile push (if push channel still routes), email pilot partners directly. |
| **Post-mortem** | Required. Owner: founder until ops hire. |
| **Verification** | `curl https://triaige.com/health` returns 200; cert expiry > 30 days; DNS records match the canonical config in `docs/DEPLOY_AND_ENV.md`. |

**Pre-incident hardening (do now, not during incident):**
- Document registrar account + ownership in 1Password / equivalent
  vault.
- Set registrar to two-factor + lock the domain.
- Enable auto-renewal at the registrar with a backup payment method.
- Add expiry alerts for the cert AND the domain registration to a
  calendar 30 days out.
- Add `triaige.com` to BetterUptime / UptimeRobot for external
  monitoring (TODO).

---

## DR drill schedule

| Drill | Cadence | Format | Owner |
|-------|---------|--------|-------|
| Tabletop walkthrough (each scenario) | Quarterly | 1-hour meeting; no actual execution; verify runbook still maps to reality | On-call |
| Fly rollback drill | Quarterly | Stage a known-bad deploy on staging, rollback, time it | Founder/ops |
| Supabase backup restore drill | Annually | Full restore to a fresh staging Supabase project, time + verify | Founder/ops + Supabase support |
| LLM kill-switch drill | Quarterly | Set `LLM_NLU_ENABLED=false` on staging during a load run; verify deterministic-only path holds | Founder/ops |
| Domain renewal check | Per cert renewal cycle (90 days for Let's Encrypt) | Confirm auto-renewal worked; manual fallback procedure documented | Founder |
| Post-mortem review | After every P0/P1 | Blameless write-up in `docs/incidents/YYYY-MM-DD-…md` per `docs/RUNBOOK.md` Post-Mortem Şablonu | Incident commander |

**Drill output requirements:**
- Each drill produces a one-line entry in `docs/incidents/README.md`.
- Any "TODO / verify" item in this runbook that proves wrong during a
  drill triggers an issue + a follow-up PR.
- Quarterly tabletop must read all 8 scenarios, even if no real
  incident hit them.

## Open resilience debt (tracked here so it's not lost)

1. Maintenance-banner feature flag for mobile (scenario 1).
2. Status page (`status.triaige.com`) (scenarios 1, 5, 8).
3. Cloudflare in front of Fly (scenario 5).
4. Tenant-disable admin API (scenario 5).
5. PII-leak heuristic alert (scenario 6).
6. KVKK notification template stored in `docs/templates/` (scenario 6).
7. Supabase backup tier verification (scenario 7).
8. External cert + domain monitoring (scenario 8).
9. Rate-limit bypass token for load tests (cross-cuts; see
   `docs/engineering/LOAD_TEST_PLAN.md`).
10. Read-cached degraded mode for ongoing sessions (scenario 1).
