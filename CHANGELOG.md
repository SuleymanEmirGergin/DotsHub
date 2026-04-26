# Changelog

Tüm önemli değişiklikler bu dosyada listelenir.

## [Unreleased]

- **Session 17 — Sağlık turizmi pivotu (additive, non-breaking):**
  - **Bridge sertleştirme:** `streaming_envelope` capability token (backend + mobile + docs üçlüsü senkronize), `/v1/triage/stream` SSE capability gating fix (gerçek contract leak kapatıldı), `GET /v1/config/capabilities` runtime drift discovery.
  - **Backend reliability:** `/health` Supabase + Redis latency probe + threshold tag, session bazlı rate limit bucket (`X-Session-Id` ile NAT-fair), `Idempotency-Key` header (SHA-256 body hash + 5 dk TTL Redis/LRU).
  - **OpenAPI ↔ FastAPI route drift CI gate** (`.github/workflows/openapi-drift.yml` + `scripts/check_openapi_drift.py`).
  - **Sağlık turizmi domain v0:** 10 prosedür kataloğu (`procedures.json`) + 8 örnek partner klinik (`clinics.json`) + 12 fit-to-travel kuralı (5 dilli) + `QUOTE`/`ITINERARY` envelope tipleri (additive, eski client'lar etkisiz). Servisler: `procedure_catalog`, `clinic_registry` (hybrid Supabase/JSON), `procedure_intent` (deterministic + opt-in LLM fallback), `fit_to_travel`, `quote_engine` (5-component weighted scorer), `itinerary_engine` (category templates + 18 activity types).
  - **Yeni route'lar:** `POST /v1/quote`, `POST /v1/quote/itinerary`, `POST /v1/quote/lead` (CRM webhook out: Slack/Make/Zapier/generic, KVKK consent-gated PII, retry policy).
  - **Supabase migration:** `health_tourism_clinics` tablosu + jsonb GIN index + soft-delete + idempotent seed script.
  - **Compliance:** [docs/HEALTH_TOURISM_COMPLIANCE.md](docs/HEALTH_TOURISM_COMPLIANCE.md) — KVKK, Sağlık Turizmi Yetki Belgesi, GDPR notları + 10 maddelik operatör eylem listesi.
  - **Test:** 641 backend test (153 yeni: 13 SSE/capability + 31 reliability + 9 OpenAPI drift + 47 health tourism services/route + 15 itinerary + 19 LLM fallback + 9 hybrid registry + 13 lead webhook); sıfır regresyon.

## [4.6.0] — 2026-04-21

- **Faz 4 backlog (F4.1–F4.6):** OpenAPI senkron (`/v1/triage/stream` SSE + `DELETE /v1/me/sessions/{session_id}` KVKK); sessions-v5 Breadcrumb + client-side CSV export; ResultScreen tesis listesi + Google Maps "Haritada aç" (5 dil i18n: facilitiesEmpty/LoadError/mapOpenError); `mobile/src/api/facilitiesClient.ts` → lazy-load; Redis rate limit tüm bucket’larda (default/admin/send_summary/llm_nlu) in-memory fallback ile.
- **Mobil:** EAS build pipeline + placeholder asset’ler + CI workflow; Settings ekranı (language/legal/about/contact); Skeleton loader’lar + error tint tokens; a11y polish (chat bubbles, form inputs, choice groups); Sentry RN SDK + KVKK-safe Session Replay; info-tint tokenization + dead legacy route temizliği.
- **Backend:** Fly.io deploy scaffold + always-on + suspend-resume tuning; CORS_ORIGINS esnek parse (JSON + CSV fallback); `triage_sessions.urgency` kolonu (PGRST204 fix); Sentry DSN haftalık smoke; pytest-benchmark baseline (T3); session_pdf %100 branch coverage (T2); session PDF admin indirme (U2); staging e2e coverage (T1); real_corpus 60.8% → 70.9% (+15 senaryo).
- **Dashboard UI (Tailwind + modern tema):** Faz 1–6 tamamlandı — tasarım token’ları, shadcn hazırlığı, tüm admin sayfaları Tailwind’e geçirildi; Inter/Source Serif 4/JetBrains Mono fontları; DASHBOARD_FAZ6_ACCESSIBILITY.md. Public landing page (U3); analytics daily summary paneli (Phase B7).
- **Observability:** Prometheus `/metrics` + Grafana Cloud dashboard + lokal stack; Fly.io agent sidecar (Phase A3); alerts-as-code + CI sync; RUNBOOK.md; incidents dizini + template.
- **Dokümantasyon:** PRIVACY_AND_SECURITY genişletildi (Terms of Service); `mobile` → `triaige` rename (bundle ID + Fly app); PLAN_DISI_ISLER_OZET.md; RELEASE_CHECKLIST / TESTING / CONTRIBUTING pnpm güncellemesi.

## [4.5.0] — 2026-02-19

- **Mobil:** ResultScreen tam i18n (result.*: disclaimer, shareTitle, urgency, pdf, feedback metinleri, uyarılar, Evet/Hayır; tr/en/de/ru/ar).
- **Plan dokümanları:** PLAN_KALAN_ADIMLAR ve PLAN_SONRAKI_FAZ güncellendi (session replay i18n, gizlilik linki, ResultScreen i18n, Maestro CI).
- **CI:** Maestro E2E opsiyonel workflow (.github/workflows/mobile-e2e.yml); mobile/.maestro değişince tetiklenir; cihaz yoksa continue-on-error.
- **Release / bakım:** RELEASE_CHECKLIST genişletildi (0. Sürüm öncesi, 4–7. CI/dokümantasyon/kod/i18n/güvenlik; checkbox’lı alt maddeler). Backend regression: send-summary/export-summary testleri REDIS_URL="" ile geçiyor (run_backend_regression.py env_override). DEPENDENCY_UPDATES.md 2026-02-19 güncellendi; mobil npm audit notu eklendi. Plan dokümanları bu release maddeleriyle güncellendi.

## [4.4.0] — 2026-02-18

- **Dashboard:** Session Replay sayfası i18n (sessionReplay.*, getLocale/getText); tuning-metrics ve tuning-report i18n tamamlandı.
- **Mobil:** Giriş ekranında gizlilik politikası linki (EXPO_PUBLIC_PRIVACY_URL; boşsa link gizli); intro.privacyLink tr/en/de/ru/ar; DEPLOY_AND_ENV ve PRIVACY_AND_SECURITY güncellendi.
- **Maestro:** triage_flow_smoke.yaml sonuç ekranına kadar genişletildi (Evet tıkla → "Yeni Değerlendirme Başlat" görünene kadar bekle); tek soru varsayımı.

## [4.3.0] — 2026-02-18

- **Backend:** Rate limit send-summary ve export-summary için 5/dk (paylaşımlı bucket); export-summary rate limit middleware'e dahil edildi. Varsayılan SEND_SUMMARY_RATE_LIMIT_MAX_REQ=5.
- **Backend:** test_summary_export_route: 5/dk'ya göre güncellendi; export-summary 429 testi (test_export_summary_429_after_limit_exceeded) eklendi.
- **Dokümantasyon:** TESTING.md (backend/dashboard/mobil test komutları, summary ve rate limit testleri); ARCHITECTURE.md ve DEPLOY_AND_ENV.md rate limit 5/dk ve export-summary güncellemesi; BUGUN_YAPILACAKLAR güncellendi.
- **Push:** PUSH_NOTIFICATIONS_POLICY.md içinde backend–mobil push-token kontratı; API_EXAMPLES.md'de push-token curl örnekleri. Mobil usePushRegistration'da device_id boş guard.
- **İsteğe bağlı:** Push API kontratı; Dashboard tuning-tasks sayfası i18n (getText). Maestro triage_flow_smoke.yaml (semptom → QUESTION). Plan dokümanları (PLAN_KALAN_ADIMLAR, PLAN_SONRAKI_FAZ) güncellendi.

## [4.2.0] — 2025-02-14

- **Mobil:** Erişilebilirlik (accessibilityLabel, accessibilityRole, accessibilityState) IntroScreen, ChatScreen, ResultScreen ve PrimaryButton'da; chat.symptomInput/symptomInputHint i18n. Maestro E2E (.maestro/intro_smoke.yaml).
- **Backend:** export-summary route integration testleri (tr, en, de locale).
- **Dashboard:** Status sayfası smoke testi (e2e/admin.spec.ts); Analytics sayfasında zarf tipi dağılımı kartı (RESULT, EMERGENCY, SAME_DAY, QUESTION, ERROR); tema notu (docs/DASHBOARD_THEME.md).
- **Dokümantasyon:** DEPLOY_AND_ENV genişletildi (rollback adımları, EAS Build, Vercel deploy); DEPENDENCY_UPDATES.md, DASHBOARD_THEME.md, RELEASE_CHECKLIST.md; plan dokümanları güncellendi.

## [4.1.0] — 2025-02-14

- **Mobil:** Dil saklama (AsyncStorage) + varsayılan dil (expo-localization); 5 dil (TR/EN/DE/RU/AR) ve Arapça RTL; Dil ekranı; Özet e-posta ve metin indirme; Error Boundary; Offline banner (NetInfo); Push token (locale backend'e gönderiliyor) ve politika metni.
- **Backend:** send-summary/export-summary locale tr|en|de|ru|ar; send-summary rate limit (10/dk); send-summary 429 unit testi; POST /v1/triage/push-token.
- **Dashboard:** i18n (NEXT_LOCALE cookie), dil değiştirici (TR/EN), app/error.tsx, app/not-found.tsx (404); sessions ve status i18n; /privacy gizlilik sayfası ve header linki.
- **Dokümantasyon:** PLAN_KALAN_ADIMLAR.md, PLAN_SONRAKI_FAZ.md, DEPLOY_AND_ENV.md, ARCHITECTURE.md, PRIVACY_AND_SECURITY.md; README Documentation bölümü.
- CONTRIBUTING.md ve docs/API_EXAMPLES.md eklendi.
- CI'da backend unit/E2E testleri açık adım olarak çalışıyor.
- Admin API için ayrı rate limit (IP bazlı, varsayılan 60/dk).

## [4.0.0] — Unified triage turn

- `POST /v1/triage/turn` tek endpoint ile oturum başlatma, cevap verme ve sonuç.
- Zarf tipleri: `EMERGENCY`, `SAME_DAY`, `QUESTION`, `RESULT`, `ERROR`.
- Rate limit: triaj ve feedback için X-RateLimit-* header'ları; Redis opsiyonel.
- `GET /v1/facilities` — tesis keşfi (specialty, city, lat/lon, limit).
- `/health` — Supabase erişim bilgisi.
- Structured logging (JSON + request_id), X-Request-ID response header.
- i18n hazırlığı (app/core/i18n.py), PII maskeleme (app/core/pii.py).
- Dashboard: dark mode, breadcrumb, tablo sıralama, CSV export, sistem durumu otomatik yenileme.
- Mobil: splash ekranı, PDF paylaşımı, daha fazla tesis, erişilebilirlik, konum izni açıklaması.

---

Format [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). Sürümler [Semantic Versioning](https://semver.org/spec/v2.0.0.html) ile uyumludur.
