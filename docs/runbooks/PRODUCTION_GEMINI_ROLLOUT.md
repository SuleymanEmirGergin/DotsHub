# Production rollout — Wiro/Gemini-3-Pro

This runbook walks through enabling the gemini-3-pro chain tier in
production. Use it the first time `WIRO_GEMINI_LLM_ENABLED=1` is
flipped on a real environment, and again after any Wiro upstream
change (model rename, auth-scheme migration, region cutover).

Estimated time: 10 minutes if everything works, 30 if you need to
investigate a smoke-test failure.

---

## 1. What this rollout enables

When `WIRO_GEMINI_LLM_ENABLED=1`:

- `quote_summary` chain consults gemini between qwen and gpt5-mini
  (the default `QUOTE_SUMMARY_LLM_PROVIDERS=qwen,gemini,gpt5_mini`
  order — gemini's wider 262K context handles richer prompts as the
  template grows).
- `gemini_llm.generate()` becomes a callable surface for any future
  feature that wants the multimodal path (up to 50 mixed image /
  video / audio files in one call).

When the flag is OFF (default):

- `quote_summary` chain skips gemini silently and goes qwen → gpt5_mini.
- Direct `gemini_llm.generate()` calls return None immediately.

There is no half-state. You can safely flip this on/off without
draining traffic.

---

## 2. Prerequisites

Confirm before flipping the flag:

| Requirement | How to verify |
|---|---|
| `WIRO_API_KEY` set in deploy env | `fly secrets list \| grep WIRO_API_KEY` (or platform equivalent) |
| `WIRO_API_SECRET` set in deploy env | Same; **required** — gemini-3-pro is on Wiro's HMAC signature surface, plain API-key-only mode 401s |
| Wiro account has gemini-3-pro credit | Login to wiro.ai → Billing → confirm balance > €5 (single call costs cents but a stuck retry loop can burn through fast) |
| Latest backend deploy includes the wrappers | `git log --grep "gemini" --oneline` shows `session 18 part 2`+ commits |

---

## 3. Smoke test BEFORE production

Run from your **local** machine (or a staging pod) with the same
WIRO_API_KEY/SECRET pair as production:

```bash
cd backend
python scripts/smoke_gemini.py
```

The script:
1. Reads credentials from env or `.env`.
2. Force-enables `WIRO_GEMINI_LLM_ENABLED=1` for the local process
   (does NOT persist anywhere — your `.env` stays untouched).
3. Sends a single Turkish text-only prompt (~50 tokens out).
4. Prints the response and exits 0 on success, 1 on any failure.

Expected output on success:

```
[smoke] prompt: Tek cümleyle, ne yaptığını söyle: ...
[smoke] response (length=180):
"Saç ekimi sonrası 7 gün süreyle başlık takılması gerektiğini ..."
OK: gemini-3-pro returned a non-empty response.
```

Failures and what they mean:

| Output | Likely cause | Fix |
|---|---|---|
| `ERROR: WIRO_API_KEY missing` | Env not loaded | `export WIRO_API_KEY=...` or check `.env` |
| `ERROR: WIRO_API_SECRET missing` | API-key-only mode would 401 | Add `WIRO_API_SECRET=...` to env |
| `FAIL: WiroAuthError` | Secret invalid / expired | Re-rotate per [WIRO_CREDENTIAL_ROTATION.md](WIRO_CREDENTIAL_ROTATION.md) |
| `FAIL: WiroTimeout` | Wiro queue saturated or model loading | Retry in 60s; if persists, check status.wiro.ai |
| `FAIL: WiroTaskError task_cancel` | Wiro-side rejected the prompt | Inspect Wiro panel → Task Detail for the cancellation reason |
| `FAIL: gemini_llm.generate returned None` | Upstream produced empty (very rare) | Re-run; if reproduces, check Wiro panel for partial output |

**Do NOT proceed to step 4 if smoke fails.** A green smoke is the
single best signal that the production flip will work.

---

## 4. Flip the flag in production

Pick the path matching your deployment platform:

### Fly.io
```bash
fly secrets set WIRO_GEMINI_LLM_ENABLED=1
# Triggers a rolling deploy. Existing in-flight quote_summary tasks
# finish on the old config; new requests get the new chain.
```

### Render / Railway
1. Open the dashboard → Environment → set `WIRO_GEMINI_LLM_ENABLED=1`.
2. Click "Manual Deploy" or wait for auto-redeploy.

### Docker compose / VPS
```bash
# On the host:
echo "WIRO_GEMINI_LLM_ENABLED=1" >> .env
docker compose up -d --no-deps backend
```

---

## 5. Verify in production (within 5 minutes)

### 5.1 Direct hit
```bash
curl -X POST https://api.<host>/v1/quote \
  -H "Content-Type: application/json" \
  -d '{
    "procedure_id": "fue_hair_transplant",
    "locale": "tr",
    "profile": {"age": 30, "sex": "male"}
  }'
```

First call returns `summary_tr=null` (cold cache → BG task
scheduled). Wait ~30s, fire again with a new Idempotency-Key:

```bash
curl -X POST https://api.<host>/v1/quote \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: prod-rollout-1" \
  -d '...same payload...' | jq '.payload.summary_tr'
```

`summary_tr` populated → chain working.

### 5.2 Confirm gemini specifically fired (not just qwen)

Force qwen unavailable to flush gemini:

```sql
-- In Supabase SQL editor; gemini fires when qwen is bypassed.
SELECT created_at, model, success, latency_ms
FROM llm_calls
WHERE nlu_source = 'quote_summary_llm'
  AND created_at > now() - interval '15 minutes'
ORDER BY created_at DESC
LIMIT 20;
```

Look for rows with `model='gemini'` and `success=true`. If only
`model='qwen'` shows up, qwen never failed — that's not a problem,
but it means you haven't fully exercised the gemini fallback.

### 5.3 Grafana

Open the operator dashboard:

- `quote_summary_total{provider="gemini",outcome="success"}` should
  start ticking up. Zero rate after 30 minutes of real traffic =
  qwen is succeeding 100% of the time and gemini never fires.
- `quote_summary_latency_seconds{provider="gemini"}` p50 should sit
  in 5-15s range; p95 < 30s.
- `QuoteSummaryHighErrorRate` alert MUST stay green. Firing it
  means gemini-side failures crossed 10% — page on-call.

---

## 6. Rollback (if anything goes sideways)

Flag flip is fully reversible:

```bash
# Fly.io
fly secrets set WIRO_GEMINI_LLM_ENABLED=0

# Render / Railway: dashboard env edit + redeploy

# Docker compose
sed -i '' 's/WIRO_GEMINI_LLM_ENABLED=1/WIRO_GEMINI_LLM_ENABLED=0/' .env
docker compose up -d --no-deps backend
```

After the deploy:

- `quote_summary` chain reverts to `qwen → gpt5_mini`.
- Already-cached `summary_tr` values from the gemini era remain in
  the cache (in-memory or Redis depending on `REDIS_URL`); they
  expire on TTL or are overwritten on regeneration. **No tombstone
  is needed** — the cached text is still product-correct, just
  produced by a different vendor.

Open a follow-up ticket capturing what failed; common causes:
1. Wiro account hit the daily credit ceiling → upgrade plan.
2. Prompt tokens too long for the operator's gemini quota tier →
   shorten the template in `services/quote_summary._PROMPT_TEMPLATE`.
3. Sustained `WiroTimeout` → Wiro upstream incident; reach out to
   support@wiro.ai with the task IDs from `llm_calls.error_type`.

---

## 7. Open questions / future work

- **Multimodal rollout**: this runbook covers text-only. When a
  feature wants gemini's 50-file multimodal path, write a separate
  rollout that exercises `input_files` + `input_urls` in the smoke
  script and verifies size caps + the Wiro queue behaviour with
  multi-file tasks.
- **Chain reordering**: if production data shows gemini consistently
  outperforms qwen on Turkish output (unlikely — qwen's Türkçe-tuned
  is the hypothesis), revisit `QUOTE_SUMMARY_LLM_PROVIDERS` default
  in `app/core/config.py`. Don't change the order without llm_calls
  data showing the reorder wins on success rate AND latency.
- **Cost dashboard**: today the only cost signal is Wiro panel's own
  billing tab. A future ticket should pull `totalcost` from
  `WiroTaskResult` into `llm_calls.cost_eur` so Grafana can graph
  cost-per-summary by provider. Out of scope for this runbook.
