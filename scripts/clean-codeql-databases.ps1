# CodeQL "multiple dataset directories" uyarisini gidermek icin
# Cursor workspace storage icindeki codeql_db klasorlerini bulup siler.
# Sonrasinda CodeQL tek temiz bir veritabani olusturur.
#
# Kullanim: PowerShell'de proje kokunden veya scripts/ icinden:
#   .\scripts\clean-codeql-databases.ps1
#   .\scripts\clean-codeql-databases.ps1 -Force   # Onay sormadan siler
#
# Not: Cursor kapaliyken calistirmaniz daha guvenli olur.

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$base = Join-Path $env:APPDATA "Cursor\User\workspaceStorage"
if (-not (Test-Path $base)) {
    Write-Host "Cursor workspaceStorage bulunamadi: $base" -ForegroundColor Yellow
    exit 1
}

# Sadece bu projeye (Dotshub) ait codeql_db'leri temizle
$projectSlug = "dotshub"
$found = @()
Get-ChildItem -Path $base -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $ws = $_.FullName
    $codeqlRoot = Join-Path $ws "GitHub.vscode-codeql"
    if (-not (Test-Path $codeqlRoot)) { return }
    Get-ChildItem -Path $codeqlRoot -Directory -Recurse -Depth 2 -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -eq "codeql_db" -and $_.FullName -match [regex]::Escape($projectSlug)) {
            $found += $_.FullName
        }
    }
}

if ($found.Count -eq 0) {
    Write-Host "Hiç codeql_db klasoru bulunamadi. CodeQL henuz calistirilmamis olabilir." -ForegroundColor Cyan
    exit 0
}

Write-Host "Bulunan codeql_db klasorleri:" -ForegroundColor Cyan
$found | ForEach-Object { Write-Host "  $_" }
Write-Host ""

if (-not $Force) {
    $r = Read-Host "Bu klasorleri silmek istiyor musunuz? (e/H)"
    if ($r -ne "e" -and $r -ne "E") {
        Write-Host "Iptal edildi." -ForegroundColor Yellow
        exit 0
    }
}

foreach ($dir in $found) {
    try {
        Remove-Item -Path $dir -Recurse -Force
        Write-Host "Silindi: $dir" -ForegroundColor Green
    } catch {
        Write-Host "Silinemedi: $dir - $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Tamam. Cursor'u acip CodeQL kullandiginizda tek bir veritabani olusturulacak." -ForegroundColor Green
