# Release checklist (sırasıyla)

Her sürüm çıkarırken aşağıdaki sırayı izleyin.

---

## 0. Sürüm öncesi

- [ ] Backend: `cd backend && python scripts/run_backend_regression.py` çalıştırıldı.
- [ ] Dashboard: `cd dashboard && pnpm run test:routes && pnpm run test:i18n-contract` çalıştırıldı.
- [ ] İsteğe bağlı: `cd dashboard && pnpm run test:e2e` (Playwright) çalıştırıldı.
- [ ] `pnpm audit` (dashboard, mobile) ve `pip list --outdated` (backend) kontrol edildi; [DEPENDENCY_UPDATES.md](DEPENDENCY_UPDATES.md) ile karşılaştırıldı. Komutlar: [DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md).
- [ ] Bu release’te biten maddeler [PLAN_KALAN_ADIMLAR.md](PLAN_KALAN_ADIMLAR.md) / [PLAN_SONRAKI_FAZ.md](PLAN_SONRAKI_FAZ.md) içinde güncellendi.
- [ ] Yeni endpoint/env varsa README, [DEPLOY_AND_ENV.md](DEPLOY_AND_ENV.md), [API_EXAMPLES.md](API_EXAMPLES.md) güncel.

---

## 1. CHANGELOG (E.1)

- `CHANGELOG.md` içinde **[Unreleased]** altındaki maddeleri yeni sürüm başlığına taşıyın.
- Yeni başlık örneği: `## [4.3.0] — YYYY-MM-DD`
- **[Unreleased]** altında sadece şu satır kalsın: `- (Yeni değişiklikler buraya.)`
- Tarih: release günü (ISO: YYYY-MM-DD).

---

## 2. Git tag

- Proje kökünde: `git tag v4.3.0` (veya ilgili sürüm).
- Push: `git push origin v4.3.0`

---

## 3. Release notu

- GitHub/GitLab release sayfasında yeni release oluşturun.
- Tag: az önce push ettiğiniz tag (örn. `v4.3.0`).
- Başlık: `v4.3.0` veya `4.3.0 — Kısa özet`.
- Açıklama: `CHANGELOG.md` içindeki ilgili sürüm maddelerini kopyalayıp yapıştırın (liste halinde).

---

## 4. CI ve operasyon (periyodik kontrol)

- [ ] [BRANCH_PROTECTION_CHECKLIST.md](BRANCH_PROTECTION_CHECKLIST.md) — required check’ler tanımlı. Branch protection ve production kontrolü **manuel adımlar** için: [POST_RELEASE_MANUEL_ADIMLAR.md](POST_RELEASE_MANUEL_ADIMLAR.md).
- [ ] `.github/workflows/secret-scan.yml` PR/push’ta çalışıyor (gerekirse workflow_dispatch ile denendi).
- [ ] `backend-regression`, `dashboard-quality` (ve varsa `dashboard-tests`) bir PR’da yeşil.

---

## 5. Dokümantasyon (gerektiğinde)

- [ ] README endpoint ve env listesi güncel.
- [ ] [CONTRIBUTING.md](../CONTRIBUTING.md) test komutları [TESTING.md](TESTING.md) ile uyumlu.
- [ ] [API_EXAMPLES.md](API_EXAMPLES.md) yeni endpoint’ler için curl örneği içeriyor.
- [ ] OpenAPI (docs/openapi_orchestrator.yaml veya kullanılan dosya) API ile senkron.

---

## 6. Kod ve i18n (isteğe bağlı)

- [ ] Mobil sabit metinler (örn. summary.tsx "Önemli Notlar") i18n key’e taşındı.
- [ ] Placeholder/label’larda Türkçe karakter düzeltmeleri yapıldı.

---

## 7. Güvenlik ve production (release öncesi kontrol)

Ayrıntılı adımlar: [GUVENLIK_RELEASE_KONTROL.md](GUVENLIK_RELEASE_KONTROL.md).

- [ ] Production’da CORS_ORIGINS gerçek origin’lerle sınırlı (env; bkz. config.py, DEPLOY_AND_ENV).
- [ ] HSTS, X-Content-Type-Options vb. (APP_ENV=production; bkz. security_headers.py, SECURITY_HEADERS_INTEGRATION).
- [ ] Admin API rate limit ve varsa IP kısıtı dokümante ve yapılandırma ile uyumlu (README, API_EXAMPLES, ADMIN_RATE_LIMIT_*).

---

## Özet sıra

0. **Sürüm öncesi** — Test, bağımlılık/güvenlik, plan dokümanları, README/doküman uyumu  
1. **CHANGELOG** — [Unreleased] → yeni `## [X.Y.Z]` bloğu  
2. **Tag** — `git tag vX.Y.Z` + push  
3. **Release** — Repo release sayfasında tag seçip not ekle  
4. **CI/operasyon** — (Periyodik) Branch protection, secret scan, workflow’lar  
5. **Dokümantasyon** — (Gerektiğinde) README, CONTRIBUTING, API_EXAMPLES, OpenAPI  
6. **Kod/i18n** — (İsteğe bağlı) Mobil sabit metin, Türkçe karakter  
7. **Güvenlik** — (Release öncesi) CORS, header’lar, admin rate limit  

Bu sıra her release’te tekrarlanır; 0, 4–7 maddeleri ihtiyaca göre uygulanır.
