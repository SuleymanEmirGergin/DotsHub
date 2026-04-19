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
npm install              # or: npm ci --legacy-peer-deps (CI)
npx expo start
```

**Package manager**: mobile uses `npm` (tracked via `package-lock.json`),
dashboard uses `pnpm` (tracked via `pnpm-lock.yaml`). The split is
deliberate:

- Mobile follows Expo's documented default (`npm ci` +
  `--legacy-peer-deps` for the Expo 54 + React 19 + RN 0.81 matrix).
  CI uses `npm` to match. Do not run `pnpm install` inside `mobile/`.
- Dashboard's Next.js + Vercel tooling plays better with `pnpm`.
  CI uses `pnpm` to match. Do not run `npm install` inside
  `dashboard/`.

The backend is Python, so it's independent of this choice.

## Mock’lar ve Ortam

- Backend: `.env` ile `WIRO_*`, `SUPABASE_*`, `REDIS_URL` vb. ayarlanır. Testlerde mock kullanılır (`unittest.mock.patch`).
- Mobil: `USE_MOCK=true` ve `API_BASE` ile backend adresi verilir.
- Dashboard: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_SUPABASE_*`, `ADMIN_API_KEY` gerekir.

## CI

- **Backend:** `.github/workflows/backend-regression.yml` — unit/E2E testler + golden flow regression.
- **Dashboard:** `.github/workflows/dashboard-quality.yml` — lint; `.github/workflows/dashboard-tests.yml` — contract (test:routes, test:i18n-contract) + Playwright E2E (dashboard değişince).
- PR’da ilgili path’ler değiştiğinde ilgili workflow tetiklenir.

## Kod Standartları

- Backend: mevcut stil (Black/ruff kullanılıyorsa proje kökündeki config’e uyun).
- TypeScript/React: dashboard ve mobile’da mevcut ESLint/TypeScript kurallarına uyun.

## Sorular

- Dokümantasyon: `README.md`, `docs/` altındaki spec’ler.
- API sözleşmesi: `docs/openapi_orchestrator.yaml`.
