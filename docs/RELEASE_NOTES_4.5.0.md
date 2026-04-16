# 4.5.0 — 2026-02-19

Aşağıdaki metni GitHub Release sayfasında "Describe this release" alanına yapıştırın.

---

- **Mobil:** ResultScreen tam i18n (result.*: disclaimer, shareTitle, urgency, pdf, feedback metinleri, uyarılar, Evet/Hayır; tr/en/de/ru/ar).
- **Plan dokümanları:** PLAN_KALAN_ADIMLAR ve PLAN_SONRAKI_FAZ güncellendi (session replay i18n, gizlilik linki, ResultScreen i18n, Maestro CI).
- **CI:** Maestro E2E opsiyonel workflow (.github/workflows/mobile-e2e.yml); mobile/.maestro değişince tetiklenir; cihaz yoksa continue-on-error.
- **Release / bakım:** RELEASE_CHECKLIST genişletildi (0. Sürüm öncesi, 4–7. CI/dokümantasyon/kod/i18n/güvenlik; checkbox’lı alt maddeler). Backend regression: send-summary/export-summary testleri REDIS_URL="" ile geçiyor (run_backend_regression.py env_override). DEPENDENCY_UPDATES.md 2026-02-19 güncellendi; mobil npm audit notu eklendi. Plan dokümanları bu release maddeleriyle güncellendi.
