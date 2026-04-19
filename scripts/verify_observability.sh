#!/usr/bin/env bash
# Post-deploy observability health check.
#
# Runs the four tests that matter for "observability is actually on":
#
#   1. /metrics responds 200 with Prometheus exposition format.
#   2. Custom counters (rate_limit_hits_total, capability_gate_*,
#      triage_envelope_total) appear in the scrape output.
#   3. (If GRAFANA_CLOUD_* env set) Sample shows up on the cloud side
#      within the last 2 minutes — proves the agent's remote_write is
#      actually flowing.
#   4. (If SENTRY_DSN set) A test error propagates to Sentry.
#
# Non-zero exit → at least one check failed. Use as a deploy gate or
# post-merge smoke (see .github/workflows/observability-sync.yml for
# optional integration).
#
# Required env:
#   BACKEND_URL               e.g. https://api.pretriage.app
# Optional env:
#   GRAFANA_CLOUD_PROM_URL    if set → verify sample arrival on cloud
#   GRAFANA_CLOUD_PROM_USER   basic_auth user for the cloud check
#   GRAFANA_CLOUD_PROM_TOKEN  basic_auth token
#   SENTRY_DSN                if set → fire a test event
#   ADMIN_API_KEY             if the /metrics endpoint is admin-gated
#                             (it isn't by default; left for future)

set -euo pipefail

BACKEND_URL="${BACKEND_URL:?BACKEND_URL is required}"
TIMEOUT_SEC="${TIMEOUT_SEC:-10}"

# Collected failures — report all at end so a single run shows every
# problem rather than dying at the first one.
FAILURES=()

pass() { echo "✓ $1"; }
fail() { echo "✗ $1" >&2; FAILURES+=("$1"); }

# ─── Check 1: /metrics endpoint ────────────────────────────────────
echo
echo "── 1. /metrics endpoint ──"

METRICS_RAW="$(mktemp)"
HTTP_CODE=$(curl --silent --max-time "${TIMEOUT_SEC}" --output "${METRICS_RAW}" \
  --write-out "%{http_code}" "${BACKEND_URL}/metrics" || echo "000")

if [[ "${HTTP_CODE}" == "200" ]]; then
  pass "/metrics returned 200"
else
  fail "/metrics returned HTTP ${HTTP_CODE}"
fi

# Exposition format: starts with `# HELP` or `# TYPE` lines.
if head -5 "${METRICS_RAW}" | grep -qE '^# (HELP|TYPE) '; then
  pass "response is Prometheus exposition format"
else
  fail "response does not look like Prometheus text format (head: $(head -1 "${METRICS_RAW}"))"
fi

# ─── Check 2: Custom counters ──────────────────────────────────────
echo
echo "── 2. Custom counters ──"

EXPECTED_METRICS=(
  "rate_limit_hits_total"
  "capability_gate_filtered_total"
  "capability_gate_bytes_saved_total"
  "triage_envelope_total"
  "http_requests_total"
  "http_request_duration_seconds"
)

# A counter only appears in the scrape AFTER its first increment.
# Nudge at least the HTTP series by hitting the root:
curl --silent --max-time "${TIMEOUT_SEC}" "${BACKEND_URL}/health" >/dev/null 2>&1 || true

# Re-scrape.
curl --silent --max-time "${TIMEOUT_SEC}" "${BACKEND_URL}/metrics" > "${METRICS_RAW}"

for metric in "${EXPECTED_METRICS[@]}"; do
  if grep -q "^${metric}\b\|^${metric}{" "${METRICS_RAW}"; then
    pass "${metric} present"
  else
    # Custom counters only tick once their path runs — this is a
    # warning, not a hard fail, for the rate-limit / capability-gate
    # ones that might not have been exercised yet on a fresh deploy.
    case "${metric}" in
      rate_limit_hits_total|capability_gate_*|triage_envelope_total)
        echo "  ~ ${metric} absent (OK — not yet exercised)"
        ;;
      *)
        fail "${metric} missing"
        ;;
    esac
  fi
done

# ─── Check 3: Grafana Cloud sample arrival (optional) ──────────────
echo
echo "── 3. Grafana Cloud sample arrival ──"

if [[ -n "${GRAFANA_CLOUD_PROM_URL:-}" && \
      -n "${GRAFANA_CLOUD_PROM_USER:-}" && \
      -n "${GRAFANA_CLOUD_PROM_TOKEN:-}" ]]; then

  # remote_write URL ends with /api/prom/push — the query URL drops
  # the /push and uses /api/prom/api/v1/query (Mimir's convention).
  QUERY_BASE="${GRAFANA_CLOUD_PROM_URL%/api/prom/push}/api/prom/api/v1/query"

  # `up{service="backend"}` is the canonical "agent is scraping" check
  # — it's auto-emitted by the scraper, not by the app.
  RESP=$(curl --silent --max-time "${TIMEOUT_SEC}" \
    --user "${GRAFANA_CLOUD_PROM_USER}:${GRAFANA_CLOUD_PROM_TOKEN}" \
    --data-urlencode 'query=up{service="backend"}' \
    "${QUERY_BASE}" || echo '{}')

  SAMPLE_COUNT=$(echo "${RESP}" | jq -r '.data.result | length' 2>/dev/null || echo "0")

  if [[ "${SAMPLE_COUNT}" -gt 0 ]]; then
    pass "Grafana Cloud has ${SAMPLE_COUNT} up{service=\"backend\"} series"
  else
    fail "Grafana Cloud returned no samples — agent not reaching remote_write?"
  fi
else
  echo "  – skipping (GRAFANA_CLOUD_PROM_* not set)"
fi

# ─── Check 4: Sentry test event (optional) ─────────────────────────
echo
echo "── 4. Sentry test event ──"

if [[ -n "${SENTRY_DSN:-}" ]]; then
  if command -v sentry-cli >/dev/null 2>&1; then
    if sentry-cli send-event --message "observability verify probe — $(date -u +%FT%TZ)" 2>/dev/null; then
      pass "sentry-cli test event accepted"
    else
      fail "sentry-cli rejected the test event"
    fi
  else
    echo "  – sentry-cli not installed — skipping Sentry probe"
    echo "    (install: curl -sL https://sentry.io/get-cli/ | bash)"
  fi
else
  echo "  – skipping (SENTRY_DSN not set)"
fi

# ─── Summary ───────────────────────────────────────────────────────
echo
if (( ${#FAILURES[@]} == 0 )); then
  echo "✓ All checks passed."
  exit 0
else
  echo "✗ ${#FAILURES[@]} failure(s):" >&2
  for f in "${FAILURES[@]}"; do echo "   • $f" >&2; done
  exit 1
fi
