# Load Test Plan — TriAIge Backend

**Owner:** emirgergin21@gmail.com (TriAIge founder)
**Audience:** founder running a load test before pilot launch; future
hire-1 ops adopting the same procedure.
**Scripts:** `tests/load/01_smoke.js`, `02_steady.js`, `03_burst.js`,
`04_sustained.js`.

## Why this exists

Acıbadem pilot at 1 branch / 100 sessions/day is trivial — a single
`shared-cpu-1x` Fly machine handles that without breathing hard. The
realistic worst case is 5 branches all opening their morning queue at
08:00, which can spike to ~50 sessions/min. Compound that with the
deterministic NLU pipeline running ~1000-pattern regex on each turn
plus every Supabase round-trip, and the question shifts from "will
this work?" to "where does it fall over first?". This plan answers
that question before a real patient lives at the wrong end of the
spike.

Two demo-prep validation passes already surfaced regex-pattern
shortcomings in `canonical_extract` under normal traffic; load-test
exposure surfaces a different class — connection pool saturation,
Supabase write back-pressure, in-process rate-limit fallback drift
under sustained Redis pressure. Each is hard to reproduce by hand.

## Tool choice — k6

We pick k6 over locust for these reasons:

- Single Go binary; no JVM, no Python venv to drift.
- Native Prometheus + Grafana integration via `--out` flags, so the
  results land in the same observability stack we already maintain
  (`docs/OBSERVABILITY.md`).
- Scripts in a JS dialect — readable for a frontend-fluent founder
  without onboarding to Python locust idioms.
- `constant-arrival-rate` executor models RPS, not VU count, which
  matches how we reason about the system.

## Targets — four scenarios

Each scenario has explicit pass/fail thresholds wired into the script
via `options.thresholds`. k6 exits non-zero on threshold breach, so a
CI run fails loudly.

### 1. Smoke — `01_smoke.js`

| Param | Value |
|-------|-------|
| Virtual users | 1 |
| Duration | 5 min |
| Pattern | 10 turns/min steady |
| Pass | p95 < 800 ms; error rate < 0.1% |

**Purpose:** baseline. If this fails, none of the others should run.
Catches: deploy-broken backend, unreachable staging URL, broken
auth/secrets.

### 2. Steady — `02_steady.js`

| Param | Value |
|-------|-------|
| Virtual users | 10 concurrent |
| Stages | ramp 5min → hold 15min → ramp-down 5min |
| Pattern | each VU runs 4-turn sessions, 2-5s inter-turn pause |
| Pass | p95 < 1500 ms, error rate < 0.5%, rate-limit-denied < 10 |

**Purpose:** models a normal pilot day. The 4-turn session pattern is
realistic — patients usually answer 3-5 questions before reaching
RESULT or EMERGENCY. Catches: connection pool saturation, Supabase
write batching needs, gradual memory creep.

### 3. Peak burst — `03_burst.js`

| Param | Value |
|-------|-------|
| Pattern | 5 RPS preheat × 5min, then 100 RPS × 60s |
| Executor | `constant-arrival-rate` |
| Pass | p95 < 3000 ms during burst, error rate < 1%, rate-limit-denied < 5% of bursted requests |

**Purpose:** models 5-branch simultaneous opening. Tests whether
TriAIge's per-IP rate limiter (which is currently per-machine
in-memory with optional Redis) thrashes under concurrent legitimate
clients sharing few outbound IPs (corporate / hospital NAT).

**Important:** if the staging machine is `shared-cpu-1x` (matches
prod), 100 RPS will push it. That is the point. If you want to test
at-prod-scale, scale staging up first:
`flyctl scale vm shared-cpu-2x --memory 1024 --app triaige-staging-backend`.

### 4. Sustained heavy — `04_sustained.js`

| Param | Value |
|-------|-------|
| Pattern | 50 RPS × 30 min |
| Executor | `constant-arrival-rate` |
| Pass | no upward p99 drift > 20% over the run window, error rate < 0.5%, no Fly machine restarts |

**Purpose:** memory leaks, slow Supabase queries that only show up
once the connection pool warms, accumulated rate-limit deque growth
in `app/rate_limit.py`, log handler back-pressure.

**Watch in a second terminal during the run:**

```bash
flyctl logs --app triaige-staging-backend
# look for: "WARN  rate_limit: Redis degraded"
# look for: "supabase httpx.ConnectTimeout"

flyctl status --app triaige-staging-backend
# look for: machine state changes or restart counts incrementing
```

## Environment isolation

**Run only against staging. Never against `triaige-backend` (prod).**

Staging URL: `https://triaige-staging.fly.dev` (provision per
`docs/OPS_STAGING_SETUP.md`). The Supabase project the staging app
points at is a dedicated one — load test traffic creates ~90k
`triage_sessions` rows in scenario 4 alone.

Pre-run cleanup (recommended before each run):

```sql
-- against STAGING_SUPABASE_DB_URL only
TRUNCATE triage_events, triage_sessions, triage_feedback CASCADE;
```

Post-run, capture row counts for cost estimation:

```sql
SELECT count(*) FROM triage_sessions
  WHERE created_at > now() - interval '1 hour';
```

## Rate-limit interactions

TriAIge has per-IP rate limits configured via:

- `RATE_LIMIT_MAX_REQ` (default 20 / 60s)
- `ADMIN_RATE_LIMIT_MAX_REQ`
- `SEND_SUMMARY_RATE_LIMIT_MAX_REQ`
- `LLM_NLU_RATE_LIMIT_MAX_REQ`

A k6 run from one machine looks like one IP to the backend. Without a
bypass mechanism, the 100-RPS burst hits the per-IP cap in the first
second and the rest of the test measures rate-limiter behavior, not
real backend throughput.

**Two viable approaches:**

1. **Bypass token (recommended).** Add an environment variable
   `RATE_LIMIT_BYPASS_TOKENS` to `app/rate_limit.py` that, when the
   request carries a header `X-Rate-Limit-Bypass: <token>`, skips
   rate-limit checks for that request. Mark these requests with a
   metric label so they don't pollute prod-shaped data. **This bypass
   does not currently exist** — it needs to be added before the load
   test can produce useful results. Tracked as a follow-up.

2. **Multi-IP runner.** Launch k6 from N different cloud regions
   simultaneously (k6 Cloud or self-hosted runners on different VPCs).
   More realistic but more setup.

Until the bypass token exists, run the burst + sustained scenarios
with `RATE_LIMIT_MAX_REQ` raised on staging:

```bash
flyctl secrets set --app triaige-staging-backend \
  RATE_LIMIT_MAX_REQ=10000 \
  ADMIN_RATE_LIMIT_MAX_REQ=10000 \
  SEND_SUMMARY_RATE_LIMIT_MAX_REQ=10000
# remember to reset after the test
flyctl secrets unset --app triaige-staging-backend \
  RATE_LIMIT_MAX_REQ ADMIN_RATE_LIMIT_MAX_REQ SEND_SUMMARY_RATE_LIMIT_MAX_REQ
```

## Observability during the test

Open these tabs before starting:

1. **Grafana dashboard** — Backend overview. The dashboard already
   exists per `docs/OBSERVABILITY.md`. Useful panels:
   - `http_request_duration_seconds` p50 / p95 / p99 by endpoint.
   - `triage_envelope_total` by `envelope_type`.
   - `rate_limit_hits_total{outcome="denied"}` rate.
   - `supabase_db_calls_total{outcome="error"}` rate.

2. **Prometheus / Grafana Explore** queries to keep handy:

   ```promql
   # p95 turn latency over the last minute
   histogram_quantile(0.95, sum by (le) (
     rate(http_request_duration_seconds_bucket{handler="/v1/triage/turn"}[1m])
   ))

   # 5xx rate
   sum(rate(http_requests_total{status=~"5.."}[1m]))
     / sum(rate(http_requests_total[1m]))

   # supabase write p99
   histogram_quantile(0.99, sum by (le, operation) (
     rate(supabase_db_latency_seconds_bucket[1m])
   ))

   # rate limit denials by bucket
   sum by (bucket) (rate(rate_limit_hits_total{outcome="denied"}[1m]))
   ```

3. **Sentry** — set environment filter to `staging`. Watch for novel
   exception classes appearing during the run.

4. **Fly metrics** — `flyctl status` and the Fly dashboard CPU/mem
   chart. Sustained CPU > 70% means scenario 4 will degrade.

## How to run

From repo root:

```bash
# Smoke first.
k6 run -e BASE_URL=https://triaige-staging.fly.dev \
       tests/load/01_smoke.js

# If smoke passes, run steady.
k6 run -e BASE_URL=https://triaige-staging.fly.dev \
       tests/load/02_steady.js

# Burst — only after raising staging rate limits (see above).
k6 run -e BASE_URL=https://triaige-staging.fly.dev \
       tests/load/03_burst.js

# Sustained — long-running; usually overnight or during low-traffic
# window. Tail flyctl logs in another terminal.
k6 run -e BASE_URL=https://triaige-staging.fly.dev \
       tests/load/04_sustained.js
```

Each script writes its summary JSON to `tests/load/results/`. That
directory is git-ignored (add to `.gitignore` if not already).

### Optional: stream metrics to Grafana Cloud

```bash
k6 run --out experimental-prometheus-rw \
       -e K6_PROMETHEUS_RW_SERVER_URL=$GRAFANA_CLOUD_PROM_URL \
       -e K6_PROMETHEUS_RW_USERNAME=$GRAFANA_CLOUD_PROM_USER \
       -e K6_PROMETHEUS_RW_PASSWORD=$GRAFANA_CLOUD_PROM_TOKEN \
       tests/load/02_steady.js
```

The k6 metrics show up alongside backend metrics, which makes
correlation trivial (k6 latency vs. server-side latency vs. supabase
latency, all on the same time axis).

## Findings template

After each run, fill in `docs/engineering/load_test_results/YYYY-MM-DD.md`:

```markdown
# Load Test — 2026-04-27

## Scenarios run
- [x] 01_smoke
- [x] 02_steady
- [x] 03_burst
- [ ] 04_sustained (skipped — staging on shared-cpu-1x, would not be representative)

## Pass/fail
| Scenario | Threshold | Actual | Pass |
|----------|-----------|--------|------|
| Smoke    | p95 < 800ms | 412ms | ✓ |
| Steady   | p95 < 1500ms | 1820ms | ✗ |

## Bottleneck identified
Steady p95 regressed because of supabase write latency. Each turn
issues two writes (session upsert + event insert). Under 10 concurrent
VUs, the supabase pool was waiting ~600ms on the second write.

## Fix sketch
- Batch the two writes into a single transaction via the supabase
  pooler, or
- Move event inserts to a background queue (acceptable since events
  are diagnostic-only, not on the critical path).

## Retest result
After batching: p95 = 980ms. Pass.

## Action items
- [ ] Open issue: supabase event-insert batching.
- [ ] Add `supabase_db_latency_seconds` p99 alert at 1.5s.
```

## Schedule

- **Quarterly cadence** for the full 4-scenario battery (smoke +
  steady mandatory; burst + sustained when staging is sized to
  prod).
- **Before any major release** that touches `triage_engine.py`,
  `canonical_extract.py`, `session_repo.py`, or rate-limit logic.
- **Ad hoc** after a Sentry burst that suggests a perf regression.

## Out of scope for v1

- Distributed multi-region load (k6 Cloud) — single-region runner is
  enough until the rate-limit bypass token lands.
- Mobile app E2E load — the mobile path adds React Native render
  cost that this plan does not measure. Separate test surface.
- Long-tail diagnostic flows (PDF export, summary email) — these are
  rate-limited to 5/min by design and are not on the critical
  triage path.
