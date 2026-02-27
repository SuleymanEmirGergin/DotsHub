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

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
```

Dashboard birim testleri (Node test runner): `cd dashboard && node --test tests/*.test.cjs`
Mobil birim testleri (Jest): `cd mobile && npm test`

Tam regression (golden flows dahil):

```bash
cd backend
python scripts/run_backend_regression.py
```

### Dashboard

```bash
cd dashboard
npm install
npm run lint
```

E2E (Playwright): `dashboard/playwright.config.ts` ve `dashboard/e2e/` mevcut. Kurulum: `cd dashboard && npm install -D @playwright/test && npx playwright install chromium`. Çalıştırma: `npx playwright test` (dev server’ı ayrı başlatın veya config’teki webServer kullanın).

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

- **Backend:** `.github/workflows/backend-regression.yml` — unit/E2E testler + golden flow regression.
- **Dashboard:** `.github/workflows/dashboard-quality.yml` — lint.
- PR’da ilgili path’ler değiştiğinde ilgili workflow tetiklenir.

## Kod Standartları

- Backend: mevcut stil (Black/ruff kullanılıyorsa proje kökündeki config’e uyun).
- TypeScript/React: dashboard ve mobile’da mevcut ESLint/TypeScript kurallarına uyun.

## Sorular

- Dokümantasyon: `README.md`, `docs/` altındaki spec’ler.
- API sözleşmesi: `docs/openapi_orchestrator.yaml`.
