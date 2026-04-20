#!/usr/bin/env bash
#
# Sentry smoke test — POSTs a synthetic event to the configured DSN,
# confirms the server accepted it (HTTP 200), and exits non-zero on
# any failure.
#
# Purpose: catch silent telemetry loss. If our Sentry DSN gets
# rotated, the project gets archived, the org key expires, or the
# free-tier quota exhausts, we want to know within a week, not
# after the next real incident when we go looking for context and
# find empty breadcrumb trails.
#
# Usage:
#   MOBILE_SENTRY_DSN=https://PUBLIC@oXXXX.ingest.sentry.io/PROJECT_ID \
#   ./scripts/sentry_smoke.sh
#
# Optional:
#   SENTRY_SMOKE_ENVIRONMENT   Tag on the synthetic event
#                              (default: ci-smoke). Does NOT match
#                              the `test` / `ci` values that the
#                              mobile beforeSend hook drops — we
#                              bypass the SDK entirely by POSTing
#                              directly, so dropping doesn't apply
#                              here either way.
#   SENTRY_SMOKE_RELEASE       Release tag (default: smoke@YYYYMMDD)
#
# Exit codes:
#   0  Event accepted (HTTP 200 from the Sentry store API)
#   1  DSN missing or malformed
#   2  Sentry rejected the event (4xx/5xx)
#   3  Dependency missing (curl / python3)
#
# The script does NOT verify downstream ingestion in the Sentry UI —
# a 200 from the store API means the DSN is valid and the project
# accepts events, which is the contract we care about for "is the
# pipe open?". Full ingestion verification would require a Sentry
# auth token with issue-read scope — overkill for a smoke test.

set -euo pipefail

DSN="${MOBILE_SENTRY_DSN:-}"
if [[ -z "$DSN" ]]; then
  echo "ERROR: MOBILE_SENTRY_DSN is not set" >&2
  exit 1
fi

# Parse `https://<public_key>@<host>/<project_id>` (Sentry DSN form).
# The regex allows hyphens and dots in the host; reject anything
# malformed up front so we don't POST to a typo'd endpoint.
if [[ ! "$DSN" =~ ^https://([^@]+)@([^/]+)/([0-9]+)$ ]]; then
  echo "ERROR: invalid DSN shape; expected https://<key>@<host>/<project_id>" >&2
  exit 1
fi
PUBLIC_KEY="${BASH_REMATCH[1]}"
HOST="${BASH_REMATCH[2]}"
PROJECT_ID="${BASH_REMATCH[3]}"

command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required" >&2; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required (uuid generation)" >&2; exit 3; }

EVENT_ID=$(python3 -c "import uuid; print(uuid.uuid4().hex)")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
ENVIRONMENT="${SENTRY_SMOKE_ENVIRONMENT:-ci-smoke}"
RELEASE="${SENTRY_SMOKE_RELEASE:-smoke@$(date -u +%Y%m%d)}"

# Payload: a minimal `info`-level event. Not an error, so this
# won't trip incident-response rules even if somebody mis-tags
# ci-smoke events into a real project.
PAYLOAD=$(cat <<JSON
{
  "event_id": "$EVENT_ID",
  "timestamp": "$TIMESTAMP",
  "platform": "other",
  "level": "info",
  "environment": "$ENVIRONMENT",
  "release": "$RELEASE",
  "message": {
    "formatted": "sentry-smoke CI ping (event_id=$EVENT_ID)"
  },
  "tags": {
    "source": "gh-actions-sentry-smoke",
    "repo": "${GITHUB_REPOSITORY:-local}",
    "run_id": "${GITHUB_RUN_ID:-local}"
  }
}
JSON
)

RESP_FILE=$(mktemp)
trap 'rm -f "$RESP_FILE"' EXIT

HTTP_STATUS=$(curl -sS -o "$RESP_FILE" -w "%{http_code}" \
  -X POST "https://$HOST/api/$PROJECT_ID/store/" \
  -H "Content-Type: application/json" \
  -H "X-Sentry-Auth: Sentry sentry_version=7, sentry_key=$PUBLIC_KEY, sentry_client=gha-smoke/1.0" \
  --data-binary "$PAYLOAD")

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "FAIL: Sentry store API returned HTTP $HTTP_STATUS" >&2
  echo "--- response body ---" >&2
  cat "$RESP_FILE" >&2
  echo >&2
  exit 2
fi

echo "OK: event accepted"
echo "  event_id=$EVENT_ID"
echo "  environment=$ENVIRONMENT"
echo "  release=$RELEASE"
echo "  project_id=$PROJECT_ID"
