#!/usr/bin/env bash
# Dependency audit: backend (pip), dashboard (npm), mobile (npm).
# Usage: ./scripts/audit-dependencies.sh [--fail-on-high]
# Exit 0 unless --fail-on-high is set and a high/critical issue is found.

set -e
FAIL_ON_HIGH=false
if [ "${1:-}" = "--fail-on-high" ]; then
  FAIL_ON_HIGH=true
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
DASHBOARD="$ROOT/dashboard"
MOBILE="$ROOT/mobile"

report() { echo "[audit] $*"; }
ok() { report "OK: $*"; }
warn() { report "WARN: $*"; }
err() { report "ERROR: $*"; }

# --- Backend (pip) ---
report "--- Backend (pip) ---"
if [ -f "$BACKEND/requirements.txt" ]; then
  if command -v pip-audit &>/dev/null; then
    (cd "$BACKEND" && pip-audit -r requirements.txt 2>/dev/null) && ok "pip-audit passed" || warn "pip-audit found issues or not run"
  else
    warn "Install pip-audit for backend audit (pip install pip-audit)"
  fi
else
  warn "No backend requirements.txt"
fi

# --- Dashboard (npm) ---
report "--- Dashboard (npm) ---"
if [ -f "$DASHBOARD/package.json" ]; then
  (cd "$DASHBOARD" && npm audit --audit-level=high 2>/dev/null) && ok "npm audit passed" || true
  if [ "$FAIL_ON_HIGH" = true ]; then
    (cd "$DASHBOARD" && npm audit --audit-level=high 2>/dev/null) || { err "Dashboard: high/critical vuln"; exit 1; }
  fi
else
  warn "No dashboard package.json"
fi

# --- Mobile (npm) ---
report "--- Mobile (npm) ---"
if [ -f "$MOBILE/package.json" ]; then
  (cd "$MOBILE" && npm audit --audit-level=high 2>/dev/null) && ok "npm audit passed" || true
  if [ "$FAIL_ON_HIGH" = true ]; then
    (cd "$MOBILE" && npm audit --audit-level=high 2>/dev/null) || { err "Mobile: high/critical vuln"; exit 1; }
  fi
else
  warn "No mobile package.json"
fi

report "Done."
