#!/usr/bin/env bash
# Sync dashboards + alert rules from the repo to Grafana Cloud.
#
# Idempotent: re-runnable on every `main` push via the
# `observability-sync.yml` GitHub Actions workflow. Also runnable
# locally for ad-hoc changes — set the three required env vars and go.
#
# Design: we use two official Grafana tools so the sync is
# dual-protocol — dashboards go via the Grafana API (dashboards are
# stored in Grafana's own DB), alert rules go via Mimir's rules API
# (Grafana Cloud runs managed Mimir for metrics and hosts the rules
# there). Mixing `grafanactl` for both dashboards and alerts is
# possible but less battle-tested than mimirtool for rules.
#
# Required env:
#   GRAFANA_CLOUD_STACK_URL    https://<slug>.grafana.net
#   GRAFANA_CLOUD_API_TOKEN    Admin API token (scope: Dashboards + Alerts)
#   GRAFANA_CLOUD_PROM_URL     Mimir remote_write URL (rules use the same endpoint)
#   GRAFANA_CLOUD_PROM_USER    Numeric instance id
#   GRAFANA_CLOUD_PROM_TOKEN   MetricsPublisher / rule write token
#
# Safety: set `DRY_RUN=1` to print what WOULD be pushed without actually
# posting. The GitHub Actions workflow runs with DRY_RUN=1 on PRs and
# the real sync only on merges to main.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASH_FILE="${ROOT}/config/grafana/dashboard-triaige.json"
ALERTS_DIR="${ROOT}/config/grafana/alerts"

DRY_RUN="${DRY_RUN:-0}"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: $name is not set" >&2
    exit 2
  fi
}

require_env GRAFANA_CLOUD_STACK_URL
require_env GRAFANA_CLOUD_API_TOKEN
require_env GRAFANA_CLOUD_PROM_URL
require_env GRAFANA_CLOUD_PROM_USER
require_env GRAFANA_CLOUD_PROM_TOKEN

echo "→ Grafana Cloud stack: ${GRAFANA_CLOUD_STACK_URL}"
echo "→ DRY_RUN=${DRY_RUN}"

# ─── Dashboard sync ────────────────────────────────────────────────
#
# The Grafana API expects a POST to /api/dashboards/db with the raw
# dashboard JSON nested under `{ "dashboard": … }`. `overwrite=true`
# is safe because we ship the dashboard JSON as the source of truth —
# anyone hand-editing in the UI is expected to commit their change.

echo
echo "── Dashboard ──"
echo "   source: ${DASH_FILE}"

if [[ ! -f "${DASH_FILE}" ]]; then
  echo "ERROR: dashboard file not found at ${DASH_FILE}" >&2
  exit 2
fi

# Strip the `__inputs` / `__requires` / `id` blocks — those are only
# used by the Grafana UI's Import dialog and cause 400s on a direct
# API push if `id` is non-null + doesn't already exist.
DASH_PAYLOAD=$(jq '{dashboard: (. | del(.__inputs, .__requires, .id)), overwrite: true, folderUid: ""}' "${DASH_FILE}")

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "   DRY_RUN: would POST $(echo "${DASH_PAYLOAD}" | wc -c) bytes to /api/dashboards/db"
else
  HTTP_CODE=$(curl --silent --output /tmp/grafana_dash_resp.json --write-out "%{http_code}" \
    -X POST "${GRAFANA_CLOUD_STACK_URL}/api/dashboards/db" \
    -H "Authorization: Bearer ${GRAFANA_CLOUD_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${DASH_PAYLOAD}")
  if [[ "${HTTP_CODE}" =~ ^2 ]]; then
    echo "   OK  (HTTP ${HTTP_CODE})"
    jq -r '"   uid=\(.uid)  version=\(.version)  url=\(.url)"' /tmp/grafana_dash_resp.json || true
  else
    echo "ERROR: dashboard sync failed (HTTP ${HTTP_CODE})" >&2
    cat /tmp/grafana_dash_resp.json >&2
    exit 1
  fi
fi

# ─── Alert rules sync ──────────────────────────────────────────────
#
# Uses mimirtool, the canonical client for Mimir's rules API. It's a
# single statically-linked binary; the GH Actions workflow installs
# it via the official release asset. For local runs, `brew install
# mimirtool` or grab the release from
#   https://github.com/grafana/mimir/releases
#
# Rule namespace: we use "triaige-backend" as the Mimir "namespace"
# (rule-group collection name). Re-running overwrites in-place — the
# `load` command deletes rule-groups not in the current file.

echo
echo "── Alert rules ──"
echo "   source: ${ALERTS_DIR}"

if ! command -v mimirtool >/dev/null 2>&1; then
  echo "WARN: mimirtool not installed — skipping alerts sync" >&2
  echo "      Install: https://grafana.com/docs/mimir/latest/manage/tools/mimirtool/" >&2
  exit 0
fi

export MIMIR_ADDRESS="${GRAFANA_CLOUD_PROM_URL%/api/prom/push}"
export MIMIR_TENANT_ID="${GRAFANA_CLOUD_PROM_USER}"
export MIMIR_API_KEY="${GRAFANA_CLOUD_PROM_TOKEN}"

for rules_file in "${ALERTS_DIR}"/*.yaml; do
  [[ -f "${rules_file}" ]] || continue
  namespace="$(basename "${rules_file}" .yaml)"
  echo "   namespace=${namespace}  file=${rules_file}"

  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "     DRY_RUN: mimirtool rules check ${rules_file}"
    mimirtool rules check "${rules_file}" || {
      echo "ERROR: rule file failed lint" >&2
      exit 1
    }
  else
    # `load` replaces the entire namespace — deterministic + idempotent.
    mimirtool rules load "${rules_file}"
    echo "     OK"
  fi
done

echo
echo "✓ Sync complete."
