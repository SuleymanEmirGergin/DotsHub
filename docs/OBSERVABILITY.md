# Observability — Metrics, Dashboards, Alerting

Two-layer stack:

1. **Errors** → Sentry (`app/observability/sentry_init.py`). Set
   `SENTRY_DSN` in the backend env and errors / performance traces
   flow automatically. No DSN = no-op SDK init; the app still runs.
2. **Metrics** → Prometheus format scraped from `GET /metrics`.
   Dashboards + alerts live in Grafana. Free-tier **Grafana Cloud**
   is the recommended production path; a local
   `docker-compose.monitoring.yml` stack exists for development.

This doc covers the metrics half. For Sentry, see the
`observability/sentry_init.py` module docstring.

## What's exposed on `/metrics`

The endpoint is mounted by `app/observability/metrics.py::setup_metrics()`
and excludes `/metrics` + `/health` from self-instrumentation (no
infinite feedback loop).

**Default HTTP series** (`prometheus-fastapi-instrumentator`):

| Metric                                  | Type      | Notes |
| --------------------------------------- | --------- | ----- |
| `http_requests_total`                   | Counter   | Labels: `method`, `handler`, `status` (grouped 2xx/4xx/5xx). |
| `http_request_duration_seconds`         | Histogram | Default buckets; use `histogram_quantile()` for p50/p95/p99. |
| `http_requests_inprogress`              | Gauge     | In-flight request count. |

**Custom domain series** (`app/observability/metrics.py`):

| Metric                                  | Type      | Labels                        | Incremented by |
| --------------------------------------- | --------- | ----------------------------- | -------------- |
| `capability_gate_filtered_total`        | Counter   | `envelope_type`, `caps_missing` | `CapabilityGateMiddleware` when a response gets fields stripped. |
| `capability_gate_bytes_saved_total`     | Counter   | —                              | Same path — aggregate bytes removed. |
| `triage_envelope_total`                 | Counter   | `envelope_type`               | Same path — one hit per envelope emitted to a reduced-capability client (see "Sampling caveat" below). |
| `rate_limit_hits_total`                 | Counter   | `bucket` ∈ `{default, admin, send_summary, llm_nlu}`, `outcome` ∈ `{allowed, denied}` | `app.rate_limit.check_*_rate_limit*` — one increment per public rate-limit decision. |
| `confidence_score`                      | Histogram | — (buckets 0.1…1.0)           | Reserved for the triage engine — call `confidence_score.observe(x)` when a RESULT envelope is emitted. |

### Sampling caveat — `triage_envelope_total`

`triage_envelope_total` is incremented inside
`CapabilityGateMiddleware.dispatch()` only on the reduced-capability
path (clients missing at least one capability in the registry). Full-
capability clients short-circuit to the fast path and are not decoded,
so they don't contribute to this counter. The metric under-reports
total envelope volume but accurately reflects gate activity. If you
need total envelope counts, move the counter to the endpoint layer
(tracked as future work).

### Label cardinality

Every label value set is bounded:

- `envelope_type` ∈ `{RESULT, EMERGENCY, QUESTION, ERROR}` — 4 values.
- `caps_missing` is the sorted comma-joined subset of
  `KNOWN_CAPABILITIES` (currently 2 capabilities → at most 3 non-full
  subsets). Grows additively as we ship new capabilities, but stays
  finite.
- `bucket` has 4 fixed values. `outcome` has 2.

Total series count across custom metrics is on the order of ~30, which
is trivial for any scraper.

## Option A — Grafana Cloud (production)

**Free tier:** 10k active series, 50 GB logs, 14-day retention. More
than enough for Dotshub's scale.

### 1. Sign up + grab remote_write credentials

1. Create a free stack at <https://grafana.com/products/cloud/>.
2. Navigate to **My Account → My Stack → Prometheus → Details**.
3. Copy:
   - `remote_write` endpoint URL (looks like
     `https://prometheus-prod-XX-prod-eu-west-X.grafana.net/api/prom/push`)
   - A new API key with `MetricsPublisher` scope.

### 2. Pick a scraper

You have two options:

#### 2a. Grafana Agent Flow sidecar (recommended)

Run the Grafana Agent next to the backend (same host / pod / Fly machine).
It scrapes `localhost:8000/metrics` every 15s and forwards to Grafana
Cloud. Minimal Alloy / Flow config:

```river
prometheus.scrape "backend" {
  targets = [
    { "__address__" = "localhost:8000" },
  ]
  metrics_path = "/metrics"
  scrape_interval = "15s"
  forward_to = [prometheus.remote_write.cloud.receiver]
}

prometheus.remote_write "cloud" {
  endpoint {
    url = env("GRAFANA_CLOUD_PROM_URL")
    basic_auth {
      username = env("GRAFANA_CLOUD_PROM_USER")
      password = env("GRAFANA_CLOUD_PROM_API_KEY")
    }
  }
}
```

Deploy the agent as a separate container / systemd unit / Fly process.

#### 2b. Backend-side `remote_write` (no agent)

`prometheus_client` can push directly — but this adds a write path
inside the request process. Prefer the agent unless the deployment
platform makes sidecars painful (Vercel functions, Lambda). Docs:
<https://prometheus.github.io/client_python/exporting/remote_write/>.

### 3. Import the dashboard

1. Grafana Cloud UI → **Dashboards → New → Import**.
2. Upload `config/grafana/dashboard-dotshub.json`.
3. When asked for the datasource, pick the Grafana Cloud Prometheus
   one (auto-provisioned under the name `grafanacloud-<stack>-prom`).

Panels:

- **HTTP**: request rate by status group, p50/p95/p99 latency.
- **Capability gate**: strip rate by envelope type, bandwidth saved.
- **Triage envelope mix**: donut of envelope types (EMERGENCY spike
  check, QUESTION stall watch).
- **Confidence score**: heatmap for distribution drift.
- **Rate limiting**: stacked allowed/denied per bucket, denied-fraction
  stat panel with yellow > 1% / red > 5% thresholds.

### 4. (Optional) Alerts

Grafana Cloud includes Alertmanager. Suggested starting rules:

```promql
# HTTP 5xx spike
sum(rate(http_requests_total{status=~"5.."}[5m])) > 0.5

# p95 latency regression
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m]))) > 2

# Rate-limit denied fraction sustained > 5%
sum(rate(rate_limit_hits_total{outcome="denied"}[10m])) /
  clamp_min(sum(rate(rate_limit_hits_total[10m])), 1) > 0.05

# EMERGENCY envelope anomaly (3x over 1h baseline)
sum(rate(triage_envelope_total{envelope_type="EMERGENCY"}[15m])) /
  clamp_min(avg_over_time(
    sum(rate(triage_envelope_total{envelope_type="EMERGENCY"}[15m]))[1h:15m]
  ), 0.01) > 3
```

Wire notifications to the same Slack / PagerDuty channel as Sentry.

## Option B — Local docker-compose stack (dev only)

For verifying panels + PromQL queries without a cloud account.

```bash
# 1. Start backend (separate terminal or via main docker-compose.yml)
cd backend && uvicorn app.main:app --reload

# 2. Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d
```

Then open:

- Prometheus: <http://localhost:9090/targets> — confirm the
  `dotshub-backend` target is `UP`.
- Grafana: <http://localhost:3001> (login `admin` / `admin`, will
  prompt for password change on first login — dismiss with `Skip`).
  The Dotshub dashboard is auto-imported via provisioning.

Teardown:

```bash
docker compose -f docker-compose.monitoring.yml down
# add -v to also wipe the persistent volumes
```

## Relevant files

| Path                                         | Role |
| -------------------------------------------- | ---- |
| `backend/app/observability/metrics.py`       | Counter/histogram definitions + `/metrics` mount via `setup_metrics()`. |
| `backend/app/observability/__init__.py`      | Re-exports so routes/middleware can `from app.observability import …`. |
| `backend/app/version_gating.py`              | Increments `capability_gate_*` and `triage_envelope_total`. |
| `backend/app/rate_limit.py`                  | Increments `rate_limit_hits_total{bucket,outcome}` at each public decision. |
| `backend/tests/test_metrics.py`              | Verifies `/metrics` mounts + custom counters tick. Part of the 100%-branch safety-critical gate. |
| `config/grafana/dashboard-dotshub.json`      | Importable Grafana dashboard (datasource via `${DS_PROMETHEUS}` templating). |
| `config/grafana/prometheus.yml`              | Local-dev Prometheus scrape config (Grafana Cloud does not read this). |
| `config/grafana/datasources.yml`             | Grafana provisioning — local Prometheus datasource. |
| `config/grafana/dashboards.yml`              | Grafana provisioning — auto-import the dashboard JSON. |
| `docker-compose.monitoring.yml`              | Local Prometheus + Grafana stack. |

## Gotchas

- **Host address on Linux Docker** — Prometheus in-container reaches
  the host via `host.docker.internal`, which works on Docker Desktop
  (mac/Windows) and on Linux Docker ≥ 20.10 because
  `docker-compose.monitoring.yml` sets `extra_hosts:
  host.docker.internal: host-gateway`. If you're on a pre-20.10 Linux
  Docker install, replace the target with your host's LAN IP in
  `config/grafana/prometheus.yml`.
- **Backend port** — the scrape config assumes `:8000`. If `uvicorn`
  runs on another port, update the target in `prometheus.yml` AND the
  backend-side health check alignment.
- **Coverage gate** — `app.observability.metrics` is in the
  safety-critical 100%-branch coverage set
  (`.github/workflows/backend-regression.yml`). Additions here must
  keep coverage green (`tests/test_metrics.py` is the anchor).
- **Optional dep graceful degrade** — `version_gating.py` and
  `rate_limit.py` import `prometheus_client` lazily via `app.observability`.
  If the dep is missing at runtime, increments become no-ops; the
  scrape endpoint 500s, but the rest of the app keeps working. This
  makes the metrics stack safe to roll out ahead of the monitoring
  plane without risking a hard dependency outage.
