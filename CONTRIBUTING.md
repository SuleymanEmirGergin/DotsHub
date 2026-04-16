# Katkıda Bulunma Rehberi

Pre-Triage Agentic AI projesine katkı için kısa rehber.

## Geliştirme Ortamı

- **Backend:** Python 3.11+, `backend/requirements.txt`
- **Mobile:** Node 18+, Expo (bkz. `mobile/package.json`)
- **Dashboard:** Node 18+, Next.js (bkz. `dashboard/package.json`)

## Branch Stratejisi

- `main` — ana dal; korumalı.
- Özellik/düzeltme için dal açın: `feature/...` veya `fix/...`.
- PR’lar `main`’e merge edilmeden önce CI geçmeli.

## Testleri Çalıştırma

Ayrıntılı komutlar ve test dosyaları: [docs/TESTING.md](docs/TESTING.md).

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
```

Pytest ile: `python -m pytest tests/ -v`. Tam regression (golden flows dahil): `python scripts/run_backend_regression.py`.

### Dashboard

```bash
cd dashboard
pnpm install
pnpm run lint
```

Contract testleri: `pnpm run test:routes`, `pnpm run test:i18n-contract`. E2E: `pnpm run test:e2e` (bkz. [docs/TESTING.md](docs/TESTING.md)).

### Mobil

```bash
cd mobile
npm install
npx expo start
```

## Mock’lar ve Ortam

- Backend: `.env` ile `WIRO_*`, `SUPABASE_*`, `REDIS_URL` vb. ayarlanır. Testlerde mock kullanılır (`unittest.mock.patch`).
- Mobil: `USE_MOCK=true` ve `API_BASE` ile backend adresi verilir.
- Dashboard: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_*`, `ADMIN_API_KEY` gerekir.

## CI

- **Backend:** `.github/workflows/backend-ci.yml` — regression (golden flow) + Supabase DB smoke (path-aware).
- **Dashboard:** `.github/workflows/dashboard-ci.yml` — quality (typecheck, contract, eslint) + E2E (Playwright).
- PR’da ilgili path’ler değiştiğinde ilgili workflow tetiklenir.

## Kod Standartları

- Backend: mevcut stil (Black/ruff kullanılıyorsa proje kökündeki config’e uyun).
- TypeScript/React: dashboard ve mobile’da mevcut ESLint/TypeScript kurallarına uyun.

## Sorular

- Dokümantasyon: `README.md`, `docs/` altındaki spec’ler.
- API sözleşmesi: `docs/openapi_orchestrator.yaml`.
