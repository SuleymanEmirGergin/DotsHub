# Bağımlılık denetimi (Dependency audit)

Tüm projelerde (backend, dashboard, mobile) güvenlik açığı taraması için script'ler kullanılabilir.

## Script'ler

- **`scripts/audit-dependencies.sh`** (Linux/macOS): `./scripts/audit-dependencies.sh`
  - `--fail-on-high`: High/critical bulunursa çıkış kodu 1 döner (CI için uygun).
- **`scripts/audit-dependencies.ps1`** (Windows): `.\scripts\audit-dependencies.ps1 [-FailOnHigh]`

## Gereksinimler

- **Backend**: `pip install pip-audit` ile `pip-audit` kurulmalı.
- **Dashboard / Mobile**: `npm audit` kullanılır (Node.js ile gelir).

## CI'da kullanım

İsteğe bağlı: workflow içinde `scripts/audit-dependencies.sh --fail-on-high` çalıştırarak high/critical bulunursa pipeline'ı kırabilirsiniz.
