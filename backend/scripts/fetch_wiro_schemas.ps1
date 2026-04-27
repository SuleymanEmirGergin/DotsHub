# fetch_wiro_schemas.ps1 -- Pull /Tool/Detail parameter schemas for the
# 5 Wiro models we still need to integrate. Output goes to
# backend/scripts/wiro-schemas.txt -- paste that file's content into the
# chat so the wrappers can be written against the exact field IDs.
#
# Usage (from backend/):
#   .\scripts\fetch_wiro_schemas.ps1
#
# Reads WIRO_API_KEY from one of:
#   1. The current $env:WIRO_API_KEY (if you've already set it)
#   2. The .env file in the script's parent directory (typical case)
#
# Never commits the key, never logs it. Output file contains schemas
# only -- safe to share.
#
# Note: this file is intentionally ASCII-only because Windows
# PowerShell 5.1 reads BOM-less UTF-8 as Windows-1252 and chokes on
# non-ASCII characters (em-dashes, smart quotes, etc.).

$ErrorActionPreference = "Stop"

# --- Resolve API key -------------------------------------------------
$ApiKey = $env:WIRO_API_KEY
if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $envPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
    if (-not (Test-Path $envPath)) {
        Write-Error ".env not found at $envPath and `$env:WIRO_API_KEY not set."
        exit 1
    }
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*WIRO_API_KEY\s*=\s*(.*)$') {
            $ApiKey = $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        Write-Error "WIRO_API_KEY not found in .env"
        exit 1
    }
}

# --- Slugs to probe --------------------------------------------------
$slugs = @(
    "google/nano-banana-pro",
    "openai/gpt-image-2",
    "openai/gpt-5-mini",
    "kristaller486/dots-ocr-1-5",
    "xai/grok-4-20"
)

$outputLines = @()

foreach ($slug in $slugs) {
    $parts   = $slug.Split('/', 2)
    $owner   = $parts[0]
    $project = $parts[1]
    $body    = @{ slugowner = $owner; slugproject = $project } | ConvertTo-Json -Compress

    $outputLines += ""
    $outputLines += "=== $slug ==="

    try {
        $resp = Invoke-RestMethod -Method Post `
            -Uri "https://api.wiro.ai/v1/Tool/Detail" `
            -Headers @{
                "Content-Type" = "application/json"
                "x-api-key"    = $ApiKey
            } `
            -Body $body

        $tool = $null
        if ($resp.tool -and $resp.tool.Count -gt 0) {
            $tool = $resp.tool[0]
        }
        if ($null -eq $tool) {
            $rawBody = $resp | ConvertTo-Json -Depth 4 -Compress
            $outputLines += "  (no tool returned -- raw body: $rawBody)"
            continue
        }

        # Flatten parameters[].items[] into a single field list.
        $items = @()
        foreach ($grp in ($tool.parameters | Where-Object { $_ })) {
            foreach ($p in ($grp.items | Where-Object { $_ })) {
                $items += [PSCustomObject]@{
                    id          = $p.id
                    type        = $p.type
                    required    = $p.required
                    default     = $p.default
                    options     = $p.options
                    min         = $p.min
                    max         = $p.max
                    description = $p.description
                }
            }
        }

        $outputLines += ($items | ConvertTo-Json -Depth 6)
    }
    catch {
        $outputLines += "  ERROR: $($_.Exception.Message)"
    }
}

$outputPath = Join-Path $PSScriptRoot "wiro-schemas.txt"
$outputLines | Out-File -FilePath $outputPath -Encoding utf8

Write-Host ""
Write-Host "Schemas written to: $outputPath" -ForegroundColor Green
Write-Host "Paste its contents into the chat to continue." -ForegroundColor Green
