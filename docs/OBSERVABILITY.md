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

Everything in this section is GitOps-managed out of the box:
- Dashboard JSON, alert rules, agent config are all in the repo.
- `.github/workflows/observability-sync.yml` pushes dashboard + alerts
  to Grafana Cloud on every `main` commit that touches
  `config/grafana/**` (gated by whether secrets are configured — if
  not, the job skips instead of failing).

### One-time user-action checklist

**You need to do this once**; everything else is automated.

1. **Create Grafana Cloud stack**  
   <https://grafana.com/products/cloud/> → *Start for free*. Note your
   stack URL (e.g. `https://dotshub.grafana.net`).

2. **Get remote_write credentials**  
   Grafana Cloud UI → **My Account → Prometheus → Sending metrics**.  
   Copy:
   - `remote_write` URL (looks like
     `https://prometheus-prod-XX-prod-eu-west-X.grafana.net/api/prom/push`)
   - Numeric user id
   - Create a new access token with **MetricsPublisher** + **Rule write**
     scopes. *(Rule-write is needed so the sync workflow can push alert
     rules. If you skip it, only dashboards sync; alerts have to be
     hand-imported.)*

3. **Create an admin API token for dashboard sync**  
   Grafana Cloud UI → **Administration → Access → Service accounts →
   New** → role: Editor. Copy the generated token.

4. **Create a Sentry project + get the DSN** (optional but recommended)  
   <https://sentry.io/> → new Python project.  
   Copy the DSN from **Project Settings → Client Keys**.

5. **Wire repo secrets** (GitHub → Settings → Secrets and variables →
   Actions):

   | Secret                       | Value |
   | ---------------------------- | ----- |
   | `GRAFANA_CLOUD_STACK_URL`    | `https://<slug>.grafana.net` |
   | `GRAFANA_CLOUD_API_TOKEN`    | the service-account token from step 3 |
   | `GRAFANA_CLOUD_PROM_URL`     | the `remote_write` URL from step 2 |
   | `GRAFANA_CLOUD_PROM_USER`    | the numeric user id from step 2 |
   | `GRAFANA_CLOUD_PROM_TOKEN`   | the MetricsPublisher/Rule-write token from step 2 |

6. **Wire runtime env on the agent host**  
   Same five values minus `GRAFANA_CLOUD_STACK_URL` + `GRAFANA_CLOUD_API_TOKEN`,
   plus:

   ```
   DEPLOYMENT_ENV=production
   BACKEND_SCRAPE_TARGET=backend:8000   # or your actual hostname
   ```

   How you wire env depends on the platform — see "Production deploy
   paths" below.

7. **Wire `SENTRY_DSN` on the backend process env**  
   Set in the same place the backend's other env vars live
   (`SUPABASE_URL`, `ADMIN_API_KEY`, etc.). The SDK auto-initialises
   on import — no other code change needed.

8. **Push a commit that touches `config/grafana/**`** (or manually
   dispatch the workflow) to kick off the first sync. The dashboard
   lands under the default folder; alerts land in the
   `dotshub-backend` namespace.

9. **(Optional) Wire Grafana Cloud alert routes** to Slack / email.
   Grafana Cloud UI → **Alerting → Contact points**. Bind to the
   severity labels the rules emit (`critical`, `warning`, `info`).

### Production deploy paths

The Grafana Agent is platform-agnostic — it's just a container that
needs network access to `backend:8000` and to Grafana Cloud. Three
common shapes:

#### Docker Compose host

```bash
# Starts the backend + agent with the agent pulling env from a .env:
docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  --env-file .env.production \
  up -d
```

`docker-compose.observability.yml` builds `config/grafana-agent/` and
attaches it to the same network as the backend (service DNS name
`backend` resolves). No code change in the main compose file.

#### Fly.io

Add a second process to `fly.toml`:

```toml
[processes]
  web   = "uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"
  agent = "/bin/alloy run /etc/alloy/config.river --server.http.listen-addr=0.0.0.0:12345"

[build.args]
  # Bake the River config into the deploy image; simpler than two images.
```

Set the five Grafana Cloud env vars + `SENTRY_DSN` via
`fly secrets set`. The agent reaches the web process via
`localhost:8000` — they share the same machine.

#### Kubernetes sidecar

Add a second container to the backend Deployment Pod spec:

```yaml
      - name: grafana-agent
        image: ghcr.io/<org>/dotshub-grafana-agent:<tag>   # or build on push
        env:
          - name: BACKEND_SCRAPE_TARGET
            value: "localhost:8000"
          - name: GRAFANA_CLOUD_PROM_URL
            valueFrom: { secretKeyRef: { name: grafana-cloud, key: prom_url } }
          - name: GRAFANA_CLOUD_PROM_USER
            valueFrom: { secretKeyRef: { name: grafana-cloud, key: prom_user } }
          - name: GRAFANA_CLOUD_PROM_TOKEN
            valueFrom: { secretKeyRef: { name: grafana-cloud, key: prom_token } }
          - name: DEPLOYMENT_ENV
            value: "production"
        resources:
          requests: { cpu: "10m", memory: "64Mi" }
          limits:   { cpu: "100m", memory: "256Mi" }
```

The agent sees the backend on `localhost:8000` because they share the
Pod's network namespace.

#### Render / Railway

Deploy `config/grafana-agent/` as a separate service pointing at the
backend's internal hostname. Both platforms provide an internal DNS so
the agent can reach the backend without going through the public LB.
Set `BACKEND_SCRAPE_TARGET` to the internal address.

### Verify the stack after deploy

After the first successful deploy, run:

```bash
BACKEND_URL=https://api.pretriage.app \
GRAFANA_CLOUD_PROM_URL=... \
GRAFANA_CLOUD_PROM_USER=... \
GRAFANA_CLOUD_PROM_TOKEN=... \
bash scripts/verify_observability.sh
```

This checks:
1. `/metrics` is 200 + Prometheus format.
2. Every expected counter/histogram is registered.
3. A sample lands in Grafana Cloud within ~2 min (proves remote_write
   is flowing).
4. A Sentry test event is accepted (if `sentry-cli` + `SENTRY_DSN` are
   present).

Non-zero exit = at least one check failed; the script lists every
failure (doesn't stop at the first).

### Sync automation

`.github/workflows/observability-sync.yml`:

- **PRs touching `config/grafana/**`** → DRY_RUN lint. mimirtool
  validates the alert-rule YAMLs, jq validates dashboard JSON
  structure, `scripts/grafana_sync.sh` prints what WOULD be pushed.
- **main pushes** → real sync. If the `GRAFANA_CLOUD_*` secrets are
  missing, the job emits a `::notice::` and skips the push — so you
  can ship the repo-side of observability before the cloud account
  exists without CI turning red.

Manual re-sync: run the workflow via **Actions → Observability Sync →
Run workflow**. Useful after rotating API tokens or repairing a
botched hand-edit in the Grafana UI.

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
| `docker-compose.observability.yml`           | Production Grafana Agent sidecar (overlay on main compose). |
| `config/grafana-agent/config.river`          | Alloy / Grafana Agent Flow scrape + remote_write config (env-driven). |
| `config/grafana-agent/Dockerfile`            | Sidecar image that bakes the River config. |
| `config/grafana/alerts/*.yaml`               | Alert rules as code (Prometheus/Mimir format). |
| `scripts/grafana_sync.sh`                    | Idempotent push of dashboards + alerts to Grafana Cloud. |
| `scripts/verify_observability.sh`            | Post-deploy health check for `/metrics` + cloud scrape + Sentry. |
| `.github/workflows/observability-sync.yml`   | PR lint + main-push auto-sync to Grafana Cloud. |

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
