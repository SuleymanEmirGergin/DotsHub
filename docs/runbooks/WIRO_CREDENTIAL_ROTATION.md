# Wiro.ai credential rotation runbook

This runbook covers planned + emergency rotation of Wiro credentials
used by every service under [`backend/app/services/ai/`](../../backend/app/services/ai/)
and the legacy [`llm_nlu_client`](../../backend/app/services/llm_nlu_client.py).
Rotate quarterly under normal cadence; immediately on any of the
emergency triggers in §3.

---

## 1. What credentials and where they live

Wiro authentication uses two paired secrets:

| Env var | Used by | Notes |
|---|---|---|
| `WIRO_API_KEY` | All `app/services/ai/*` + legacy `llm_nlu_client` | Public-ish identifier, sent as `x-api-key` |
| `WIRO_API_SECRET` | `app/services/ai/*` only (HMAC signature auth) | The crown jewel. **Required** for new AI services; legacy `llm_nlu_client` falls back to API-key-only mode if blank |

Both are read by `app/core/config.py` from the deployment env
(Fly.io / Render / Docker secrets — wherever the production
backend runs). Never check secrets into git; never log them.

---

## 2. Planned rotation (quarterly)

Run on the first Tuesday of every quarter. ~10 minutes if nothing
goes wrong; budget 30.

### 2.1 Generate new credentials in Wiro panel

1. Sign in to <https://wiro.ai> with the operator service account.
2. **Project → API Keys → Create new key**. Wiro returns the new
   `(api_key, api_secret)` pair. **Copy both immediately** — secret
   is shown once.
3. Note the key id (last 4 chars) for the audit trail; you'll need
   it in step 5.

### 2.2 Stage in deployment env without removing the old pair

The old key must keep working until every running instance picks up
the new one. Deployment platforms differ:

- **Fly.io**: `fly secrets set WIRO_API_KEY=... WIRO_API_SECRET=...`
  triggers a rolling deploy. The old secret stays active on Wiro's
  side until you revoke it in step 5.
- **Render / Railway**: update env in dashboard, manual redeploy.
- **Docker compose / VPS**: edit `.env`, `docker compose up -d` to
  pick up the new env. Gracefully drains existing connections.

Do NOT revoke the old key in Wiro yet.

### 2.3 Smoke-test the new credentials

After deployment finishes (rolling complete on every instance):

```bash
# Health endpoint — sanity check the backend is up.
curl -s https://api.<host>/health | jq .

# Trigger a real Wiro call — quote_summary path is the easiest.
# Set QUOTE_SUMMARY_LLM_ENABLED=1 if not already on; then:
curl -s -X POST https://api.<host>/v1/quote \
  -H "Content-Type: application/json" \
  -d '{
    "procedure_id": "fue_hair_transplant",
    "locale": "tr",
    "profile": {"age": 30, "sex": "male"}
  }'

# First request returns summary_tr=null and schedules a BG task.
# Wait 30s, fire again with a different Idempotency-Key:
curl -s -X POST https://api.<host>/v1/quote \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: rotation-smoke-1" \
  -d '...same payload...' | jq '.payload.summary_tr'
```

Cached `summary_tr` populated → new credentials work.

Alternatively, query Grafana / Supabase directly:

```sql
-- Did the last 5 minutes of llm_calls succeed?
SELECT provider, model, success, count(*)
FROM llm_calls
WHERE created_at > now() - interval '5 minutes'
GROUP BY 1,2,3
ORDER BY 4 DESC;
```

Expect non-zero rows with `success=true`. If every recent row is
`success=false` and `error_type="http_error"`, the new credentials
didn't take — check the deployment env was actually updated.

### 2.4 Update `.env.example` if rotation surfaced any new policy

If Wiro added a new auth header or rate-limit tier during this
quarter, document it in [`backend/.env.example`](../../backend/.env.example)
and [DEPLOY_AND_ENV.md](../DEPLOY_AND_ENV.md). Otherwise skip this
step.

### 2.5 Revoke the old credential pair

Only after step 2.3 confirmed the new pair works in production:

1. Wiro panel → **API Keys → Revoke** the old key id.
2. Wait 1 minute. Re-run the smoke test from §2.3 to confirm
   nothing breaks.
3. Append an entry to the rotation audit log (Slack #ops or wherever
   your team tracks):
   ```
   YYYY-MM-DD: rotated WIRO_API_KEY/SECRET.
   Old key id: ****abcd (revoked).
   New key id: ****wxyz (active).
   Verified by: <name>.
   ```

---

## 3. Emergency rotation triggers

Rotate immediately, do NOT wait for the quarterly cycle, when any of
the following are observed:

| Trigger | Detection | First step |
|---|---|---|
| Credentials checked into a public repo / pasted to Slack / leaked in a screenshot | GitHub secret scanning alert, code review, manual report | §3.1 — break-glass |
| Repeated `WiroAuthError` in logs without an obvious cause | `app.services.ai.*.auth_missing` log lines OR `llm_calls.error_type="http_error"` spike | §3.1 |
| Wiro support reports unusual usage on the operator account | Wiro email / dashboard anomaly | §3.1 |
| Operator service account password is rotated or known to be compromised | Service-account incident | §3.1 + rotate the account password too |

### 3.1 Break-glass

1. **Do NOT delete the old key first.** Generate a new pair (§2.1).
2. Stage immediately (§2.2) — skip the smoke test if the deploy
   automatically rolls; verify post-deploy.
3. Smoke test (§2.3).
4. Revoke the OLD pair (§2.5) — yes, even if new traffic isn't
   fully on it yet, accept the brief window of failed requests.
   The compromised secret being live is worse than a few minutes
   of failed Wiro calls.
5. **Audit:** pull `llm_calls` for the last 7 days, look for
   anomalies (unusual model usage, spike in input_tokens, calls
   originating off your normal traffic pattern).
6. File an incident report with timeline, scope, what was rotated,
   any user-facing impact.

---

## 4. What breaks if the rotation goes wrong

- Every `app/services/ai/*` wrapper returns `None` (fail-loud at
  `wiro_client.require_signature_auth`, caught and surfaced as `None`
  by the wrapper). Patient-facing impact:
  - `/v1/quote` still returns the ranked clinics (deterministic
    pipeline). `summary_tr` stays `None`.
  - `/v1/triage/turn` still works on the deterministic synonym
    matcher. Procedure-intent LLM fallback (`procedure_intent_llm`)
    fails — patients with edge-case Turkish input get
    `PROCEDURE_UNRESOLVED` instead of the LLM-rescued match.
- Legacy `llm_nlu_client` falls back to **API-key-only mode** if
  `WIRO_API_SECRET` is blank. This works on older Wiro projects
  but the new model surface (qwen, gemini, whisper, etc.) returns
  401. So a wrong-secret rotation still degrades the new services.
- Grafana alerts that fire:
  - `QuoteSummaryHighErrorRate` (10m / 10%)
  - `QuoteSummaryHighEmptyRate` (15m / 30%) — secondary signal
  - `LLMNluSuccessRateLow` (15m / <80%) — primary procedure-intent
    chain

Roll back: re-stage the OLD secret (you didn't revoke it, right?
§2.2 said don't), redeploy, verify recovery.

---

## 5. Open questions / future work

- **Multi-instance cache invalidation**: `quote_summary` LRU cache
  is per-process. After rotation, stale Wiro task IDs in the cache
  aren't an issue (we cache the OUTPUT text, not the task), but if
  a future change caches task references the cache must be flushed
  on rotation. Track in a separate ticket if/when this matters.
- **Read-only credentials**: Wiro doesn't currently support scoped
  keys (read-only / specific-model-only). When they do, downgrade
  the dashboard's image-gen key to a scoped one and keep the full
  key only on the backend.
- **Secret manager integration**: today we use platform env vars.
  If the operator team standardises on AWS Secrets Manager / HashiCorp
  Vault / Doppler, swap `app/core/config.py` to read from there with
  rotation-aware caching. Out-of-scope for this runbook.
