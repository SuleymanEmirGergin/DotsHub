# Plan dışı işler — yapılanlar

Release, CI ve dokümantasyonla ilgili yapılan güncellemelerin özeti.

---

## 1. CI — Mobile E2E (Maestro)

**Dosya:** `.github/workflows/mobile-e2e.yml`

- Maestro test dosyası repo kökünde değil `mobile/.maestro/` altında olduğu için workflow güncellendi.
- Test komutu: `maestro test mobile/.maestro/triage_flow_smoke.yaml`
- Yerel çalıştırma notu: `cd mobile` sonrası `maestro test .maestro/triage_flow_smoke.yaml`

---

## 2. Release checklist ve komutlar

**Dosyalar:** `docs/RELEASE_CHECKLIST.md`, `docs/TESTING.md`, `CONTRIBUTING.md`

- Dashboard için **pnpm** kullanımına geçildi (npm yerine):
  - Sürüm öncesi: `cd dashboard && pnpm run test:routes && pnpm run test:i18n-contract`
  - İsteğe bağlı E2E: `cd dashboard && pnpm run test:e2e`
  - Audit: `pnpm audit` (dashboard, mobile)
- TESTING.md ve CONTRIBUTING.md içindeki dashboard komutları pnpm ile uyumlu olacak şekilde güncellendi.

---

## 3. Sürüm öncesi testler (çalıştırıldı)

- **Dashboard:** `pnpm run test:routes` ve `pnpm run test:i18n-contract` — geçti.
- **Backend:** `cd backend && python scripts/run_backend_regression.py` — geçti (golden flow, test suite, kaggle mapping guardrails).

---

## 4. Referans dokümanlar

- RELEASE_CHECKLIST’te atıf edilen dokümanlar mevcut: BRANCH_PROTECTION_CHECKLIST.md, POST_RELEASE_MANUEL_ADIMLAR.md, GUVENLIK_RELEASE_KONTROL.md, DEPENDENCY_UPDATES.md, SECURITY_HEADERS_INTEGRATION.md, API_EXAMPLES.md, TESTING.md, CONTRIBUTING.md.

---

## Sonraki adımlar (manuel)

- Release çıkarırken: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) sırasına uyun.
- Güvenlik: [GUVENLIK_RELEASE_KONTROL.md](GUVENLIK_RELEASE_KONTROL.md) (CORS, header’lar, admin rate limit).
- Branch protection ve production: [POST_RELEASE_MANUEL_ADIMLAR.md](POST_RELEASE_MANUEL_ADIMLAR.md).
