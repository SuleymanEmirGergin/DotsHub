# Runbook: LLM Provider Down (Wiro / Anthropic / OpenAI / Google)

## Quick checklist (incident started → green)

- [ ] Confirm alert is real (not a false-positive from low traffic)
- [ ] Grab the `top_error` from the webhook alert body (timeout /
      http_error / rate_limit)
- [ ] Check status page of the active provider (Wiro / Anthropic)
- [ ] Decision: flip `LLM_NLU_ENABLED=false` OR switch `LLM_PROVIDER`
      to a healthy alternative
- [ ] Redeploy / reload config
- [ ] Watch rolling-window rate for 10 min — should recover to >80%
- [ ] Ping #dotshub-ops with timeline
- [ ] Open a post-incident ticket (see bottom)

## Symptoms (how you know)

- **Slack / Discord alert** fires from `send_llm_health_alert()` —
  "LLM NLU başarı oranı düştü: %X" — threshold default 80%, window 20 calls.
- **Admin analytics** `/admin/analytics` → "LLM NLU Health" card
  shows red border + success rate <80%.
- **Error types** on the card: `llm_http_error` dominates (auth /
  network) or `llm_timeout` spikes (provider latency).
- **Session detail** `/admin/sessions/[id]` → "LLM Çağrıları"
  table — red rows stack up for recent sessions.

## Severity

- **P2 — degraded, not broken.** Triage keeps serving because
  `services/llm_nlu.py` falls back to deterministic extraction on
  every LLM failure. Routing is unaffected; only the confidence /
  canonical-richness of the merged result is reduced.
- **P1** only if deterministic accuracy also regresses visibly
  (real_corpus pass rate drops) — see "Escalation" below.

## Immediate mitigation (< 5 min)

1. Set `LLM_NLU_ENABLED=false` in the backend env and redeploy
   (or hot-reload if the host supports it). This stops every new
   turn from attempting the broken provider and burning cost.
2. Verify: one new triage turn should now produce `nlu_source =
   "deterministic"` in the session detail LLM-calls table (no new
   rows, or only success rows).
3. Post to the incident channel: "LLM NLU flag OFF at <timestamp>.
   Triage continues on deterministic path. Investigating."

## Root-cause triage (< 15 min)

Check provider in this order:

### a) Auth regression

```bash
# Backend shell — inspect the HMAC headers the sync client would send.
python -c "
from app.services.llm_nlu_client import _wiro_auth_headers
h = _wiro_auth_headers()
print({k: (v[:8]+'...' if len(v)>12 else v) for k,v in h.items()})
"
```

Expected: `{'x-api-key': '...', 'x-nonce': '...', 'x-signature': '...'}`.
If any of these is missing or empty, check that both `WIRO_API_KEY`
and `WIRO_API_SECRET` are set in the env. The fix is an env
rotation — no code change.

### b) Provider status page

- Wiro: https://status.wiro.ai (or vendor equivalent)
- Anthropic: https://status.anthropic.com
- OpenAI: https://status.openai.com

If the provider is experiencing an incident, wait it out — don't
attempt to hot-swap providers under pressure.

### c) Project-level permission

Sample error message: `tool-not-accessible`. Means the API key is
valid but the project doesn't have access to `LLM_NLU_MODEL`
(e.g. `google/gemini-2-5-flash`). Open the provider dashboard
and enable the model for this project, or point
`LLM_NLU_MODEL` at an enabled one.

### d) Rate limit

`llm_rate_limit` dominates the error types? Raise
`LLM_NLU_RATE_LIMIT_MAX_REQ` (default 30 per 60s). Inspect recent
turn volume from admin analytics to confirm it's a real burst,
not a leak.

## Recovery

1. Root cause addressed → flip `LLM_NLU_ENABLED=true`, redeploy.
2. Monitor the LLM Health card for 10 min. Success rate should
   climb back above 80% before the next alert cool-down expires.
3. If it climbs: post "RECOVERED at <timestamp>. Cause: <one line>."
4. If it doesn't: re-flip flag OFF and escalate.

## Escalation

- Real_corpus pass rate drops by > 5 points in a rerun of
  `scripts/shadow_eval.py`: deterministic extraction alone is
  insufficient. Get an eng-on-call.
- EMERGENCY envelope rate drops by > 30% sustained: investigate
  whether the provider outage is somehow suppressing curated
  canonicals. Check `docs/TRIAJ_GOLDEN_FLOWS_17_25.md` for the
  rule-vs-canonical flow.

## Forensics (after the incident)

- `llm_calls` Supabase table rows for the incident window — error
  type breakdown, latency p95.
- Notifier webhook log (Slack / Discord channel history).
- Save a copy of the admin LLM Health card screenshot + the session
  detail red-row stack for the postmortem.

## Prevention

- Keep the `LLM_HEALTH_ALERT_COOLDOWN_SEC` > provider's typical
  incident duration (default 900s / 15 min) so we page once per
  incident, not ten times.
- Run `scripts/shadow_eval.py` in pre-release CI to catch auth
  regressions before merge.

## Post-incident checklist

- [ ] **Timeline**: detected at, mitigated at, green at (from
      webhook timestamps)
- [ ] **Root cause**: one sentence — provider outage / auth rotation
      missed / rate-limit change / our bug
- [ ] **Impact**: how many sessions got deterministic-only
      (query `llm_calls` for the window, count `success=false`)
- [ ] **What went well** / **what didn't**: 3 bullets each
- [ ] **Action items**: opened tickets for prevention (widen shadow
      eval, bump cooldown, etc.)
- [ ] Link the postmortem doc from the alert's Slack thread so
      future ops can find it
- [ ] Close the incident in ops tracker
