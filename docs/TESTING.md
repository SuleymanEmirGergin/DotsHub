# Testler

Backend, dashboard ve mobil için test komutları ve ilgili dosyaların kısa açıklaması.

---

## Backend (FastAPI, pytest)

### Çalıştırma

```bash
cd backend
python -m pytest tests/ -v
```

Belirli bir dosya veya sınıf:

```bash
python -m pytest tests/test_summary_export_route.py -v
python -m pytest tests/test_summary_export_route.py::SendSummaryRateLimitTests -v
```

### Önemli test dosyaları

| Dosya | Açıklama |
|-------|----------|
| `tests/test_summary_export_route.py` | send-summary ve export-summary route testleri: 200/404/422, locale, **rate limit 5/dk** (send-summary ve export-summary 429 testleri). |
| `tests/test_email_summary_service.py` | Özet e-posta servisi (içerik, Resend entegrasyonu mock’lu). |
| `tests/test_export_summary_service.py` | `build_export_text` unit testleri (locale, metin üretimi). |
| `tests/test_triage_turn_e2e.py` | Triage turn E2E; rate limit header’ları. |
| `tests/test_push_token_route.py` | Push token kayıt/silme endpoint’leri. |
| `tests/test_admin_v5_auth.py` | Admin API yetkilendirme. |

Rate limit (5/dk): `send-summary` ve `export-summary` aynı bucket’ı paylaşır; IP başına toplam 5 istek/dakika. Tam regression: `python scripts/run_backend_regression.py` (backend_test_suite adımı `REDIS_URL=""` ile çalışır; rate limit testleri in-memory ile geçer).

---

## Dashboard (Next.js)

### Komutlar

```bash
cd dashboard
pnpm run test:routes          # Admin proxy contract (scripts/check_admin_proxy_contract.cjs)
pnpm run test:i18n-contract   # Deployments i18n contract (scripts/check_deployments_i18n_contract.cjs)
pnpm run test:e2e             # Playwright E2E (yerelde dev server otomatik başlar)
pnpm run test:e2e:ui          # Playwright E2E (UI modu)
```

E2E testler: `dashboard/e2e/` (örn. `admin.spec.ts`). Yerelde `pnpm run test:e2e` çalıştırıldığında Playwright config (`playwright.config.ts`) dev server’ı `pnpm run dev` ile başlatır; `PLAYWRIGHT_BASE_URL` ile farklı URL verilebilir. CI’da `.github/workflows/dashboard-tests.yml` dashboard değişince contract testleri + Playwright E2E (chromium) çalıştırır; pnpm kullanır.

---

## Mobil (Expo, Jest + Maestro E2E)

### Birim testler

```bash
cd mobile
npm test
```

Birim testler: `__tests__/` ve `*.test.ts` dosyaları (örn. pushClient, i18n).

### Maestro E2E

[Maestro CLI](https://maestro.mobile.dev/) kurulu olmalı. Uygulama cihazda veya emülatörde yüklü (örn. `npx expo run:ios` / `run:android`).

```bash
cd mobile
maestro test .maestro/intro_smoke.yaml
maestro test .maestro/triage_flow_smoke.yaml
```

| Senaryo | Açıklama |
|---------|----------|
| `intro_smoke.yaml` | Uygulama açılır, "Başla" görünür. |
| `triage_flow_smoke.yaml` | Intro geçilir, semptom metni girilir ("baş ağrısı"), "Gönder" tıklanır; QUESTION ekranında "Evet" tıklanır; sonuç ekranında "Yeni Değerlendirme Başlat" görünene kadar beklenir (backend erişilebilir olmalı; tek soru varsayımı). |

CI’da opsiyonel: `.github/workflows/mobile-e2e.yml` — `mobile/` veya `.maestro/` değişince Maestro CLI kurulur ve smoke çalıştırılır; cihaz/emülatör yoksa adım fail eder (continue-on-error). Gerçek E2E için yerel veya Maestro Cloud kullanın.
