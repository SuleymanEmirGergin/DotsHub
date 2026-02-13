# Dependency audit: backend (pip), dashboard (npm), mobile (npm).
# Usage: .\scripts\audit-dependencies.ps1 [-FailOnHigh]

param([switch]$FailOnHigh)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Backend = Join-Path $Root "backend"
$Dashboard = Join-Path $Root "dashboard"
$Mobile = Join-Path $Root "mobile"

function Report { param($msg) Write-Host "[audit] $msg" }
function Ok { param($msg) Report "OK: $msg" }
function Warn { param($msg) Report "WARN: $msg" }
function Err { param($msg) Report "ERROR: $msg" }

# Backend
Report "--- Backend (pip) ---"
if (Test-Path (Join-Path $Backend "requirements.txt")) {
  try {
    Push-Location $Backend
    pip-audit -r requirements.txt 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "pip-audit passed" } else { Warn "pip-audit found issues" }
  } catch { Warn "pip-audit not available" }
  finally { Pop-Location }
} else { Warn "No backend requirements.txt" }

# Dashboard
Report "--- Dashboard (npm) ---"
if (Test-Path (Join-Path $Dashboard "package.json")) {
  Push-Location $Dashboard
  try {
    npm audit --audit-level=high 2>$null
    if ($FailOnHigh -and $LASTEXITCODE -ne 0) { Err "Dashboard: high/critical vuln"; exit 1 }
  } finally { Pop-Location }
} else { Warn "No dashboard package.json" }

# Mobile
Report "--- Mobile (npm) ---"
if (Test-Path (Join-Path $Mobile "package.json")) {
  Push-Location $Mobile
  try {
    npm audit --audit-level=high 2>$null
    if ($FailOnHigh -and $LASTEXITCODE -ne 0) { Err "Mobile: high/critical vuln"; exit 1 }
  } finally { Pop-Location }
} else { Warn "No mobile package.json" }

Report "Done."
