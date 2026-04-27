# Sonraki faz – Yapılacaklar planı

**Faz 1 tamamlandı.** Tüm zorunlu adımlar (dil, error boundary, push, dashboard i18n, test/dokümantasyon) uygulandı. Bu belge, kalan iyileştirmeleri ve yeni hedefleri sıralar.

---

## Özet: Ne kaldı?

| Tür | Durum |
|-----|--------|
| Zorunlu iş | **Yok** – Faz 1 bitti. |
| İsteğe bağlı (mevcut listeden) | A.1 push dokümanı, A.2 tuning-tasks i18n, B.1 triage_flow_smoke, CHANGELOG [Unreleased] dolduruldu. |
| Yeni hedefler | Aşağıdaki Faz 2 maddeleri. |

---

## Faz 2 – Önerilen yapılacaklar

Öncelik sırasıyla; her blok bağımsız seçilebilir.

### A. Kalite ve uyum (kısa vadeli)

| # | Yapılacak | Detay | Öncelik |
|---|-----------|--------|--------|
| A.1 | Mobil push API uyumu | Backend’in `push-token` endpoint’i (device_id, body formatı) ile mobil `pushClient` / `usePushRegistration` tam uyumunu kontrol et; gerekirse güncelle. ✅ | Orta |
| A.2 | Dashboard sayfa i18n | Admin sayfalarında (sessions, status, analytics, login, vb.) metinleri `getText(locale, "…")` ile messages’tan al; TR/EN tutarlılığı. ✅ | Düşük |
| A.3 | Release hazırlığı | CHANGELOG [Unreleased] → yeni sürüm (örn. 4.1.0) notuna taşı; git tag; release notu özeti. ✅ | Orta (release zamanı) |

### B. Test ve güvenilirlik

| # | Yapılacak | Detay | Öncelik |
|---|-----------|--------|--------|
| B.1 | Mobil E2E | Kritik akış için E2E (semptom girişi → sonuç ekranı); Maestro triage_flow_smoke.yaml sonuç ekranına kadar; CI’da opsiyonel job (mobile-e2e.yml). ✅ | Düşük |
| B.2 | Backend integration testleri | Örn. send-summary Redis ile rate limit; export-summary farklı locale; push-token 422/200. ✅ (export-summary tr/en/de integration testleri eklendi.) | Düşük |
| B.3 | Dashboard smoke | Kritik sayfaların yüklenmesi (sessions, status); Playwright/Cypress isteğe bağlı. ✅ (e2e/admin.spec.ts status testi eklendi.) | Düşük |

### C. Kullanıcı deneyimi ve erişilebilirlik

| # | Yapılacak | Detay | Öncelik |
|---|-----------|--------|--------|
| C.1 | Mobil erişilebilirlik | Ekran okuyucu etiketleri (accessibilityLabel), kontrast, odak sırası; RTL ile uyum. ✅ (IntroScreen, ChatScreen, ResultScreen, PrimaryButton.) | Düşük |
| C.2 | Mobil performans | Liste sayfalarında gerekiyorsa flatList optimizasyonu; büyük metinlerde kısaltma. ✅ (ChatScreen, HistoryScreen zaten FlatList.) | Düşük |
| C.3 | Dashboard karanlık mod tutarlılığı | Tüm sayfalarda tema değişiminde renklerin tutarlı olması. ✅ (docs/DASHBOARD_THEME.md; var(--dash-*) kullanımı.) | Düşük |

### D. Ürün ve operasyon

| # | Yapılacak | Detay | Öncelik |
|---|-----------|--------|--------|
| D.1 | Gizlilik / KVKD metni | Uygulama içi “Gizlilik politikası” sayfası veya link; PRIVACY_AND_SECURITY ile uyumlu kısa özet. ✅ | Orta |
| D.2 | Kullanım / analytics (opsiyonel) | Anonim kullanım istatistikleri (örn. sonuç türü dağılımı); backend veya dashboard’da basit grafik. ✅ (Analytics: zarf tipi dağılımı kartı.) | Düşük |
| D.3 | Deploy runbook genişletme | DEPLOY_AND_ENV’e rollback adımları, mobil build (EAS) notları, dashboard deploy (Vercel/benzeri). ✅ | Düşük |

### E. Bakım

| # | Yapılacak | Detay |
|----|-----------|--------|
| E.1 | CHANGELOG | Her release’te [Unreleased] maddelerini sürüm başlığına taşı. ✅ (docs/RELEASE_CHECKLIST.md; 0. Sürüm öncesi, 4–7, checkbox’lar eklendi.) |
| E.2 | Plan dokümanları | PLAN_KALAN_ADIMLAR.md ve PLAN_SONRAKI_FAZ.md’yi tamamlanan maddelere göre güncelle. ✅ |
| E.3 | Bağımlılık güncellemeleri | Periyodik `npm outdated` / `pip list --outdated`; güvenlik güncellemeleri öncelikli. ✅ (docs/DEPENDENCY_UPDATES.md; 2026-02-19 güncellendi, mobil npm audit notu eklendi.) | 

---

## Faz 3 – Startup hazırlığı (kritik güvenlik yamaları)

Demo ve canlı kullanım öncesi acil-tetikleyici (red flag) kurallarında çıkan bug'ların yamaları. Her madde işaretlendiğinde commit hash ile birlikte not edilir.

| # | Yapılacak | Detay | Durum |
|---|-----------|--------|--------|
| C.6 | Türkçe morfoloji: göğüs ağrısı acil tetikleyicileri | `rules.json` chest_pressure_sweating + chest_pain_plus_breathlessness + stroke_signs regex'leri ünlü düşmesi (`göğüs → göğsüm/göğsümde`), 1. tekil iyelik dative (`kola → koluma`) ve çene dative (`çeneme/çeneye`) formlarını yakalayacak şekilde genişletildi. Kol güçsüzlüğünde 1. tekil iyelik (`kolumu kaldıramıyorum`) eklendi. Regression: `backend/tests/test_emergency_rules_turkish_morphology.py` (34 yeni test). ✅ (commit `9f2b2b0`) |

---

## Faz 4 – Kalan işler planından (sonraki sprint backlog)

Aşağıdaki maddeler “Kalan işler planı” Faz 4 ile eşleşir; sprint planına göre tek tek alınabilir.

| # | Yapılacak | Detay |
|---|-----------|--------|
| F4.1 | OpenAPI senkron | ✅ `docs/openapi_orchestrator.yaml`'a `/v1/triage/stream` (SSE) ve `DELETE /v1/me/sessions/{session_id}` (KVKK data rights) path'leri eklendi. |
| F4.2 | Dashboard: breadcrumb | ✅ Tüm admin alt sayfalarında `Breadcrumb` mount; sessions-v5 dahil. |
| F4.3 | Dashboard: tablo iyileştirmeleri | ✅ Sessions + tuning-tasks (sort + filter + CSV); sessions-v5 client-side CSV export butonu. |
| F4.4 | Mobil: tesis harita linki | ✅ ResultScreen `FacilitiesCard` içinde her satırda "Haritada aç" butonu (`Linking.openURL` + Google Maps URL). |
| F4.5 | Mobil: daha fazla tesis | ✅ `mobile/src/api/facilitiesClient.ts` → `GET /v1/facilities`; ResultScreen lazy-load + 5 dil i18n. |
| F4.6 | Backend: Redis rate limit | ✅ `rate_limit.py` — default, admin, send_summary, llm_nlu bucket'larının hepsi Redis + in-memory fallback ile; main.py lifecycle'da `redis_client` wired. |

---

## Uygulama sırası önerisi

1. **Hemen yapılabilecekler:** A.1 (push uyumu), A.3 (release zamanı).
2. **Sprint içi:** A.2 (dashboard i18n), D.1 (gizlilik metni).
3. **İsteğe bağlı / uzun vadeli:** B.1–B.3, C.1–C.3, D.2–D.3, E.

---

## Tamamlanma işaretleme

Bu planda bir madde tamamlandığında ilgili satırın sonuna **✅** eklenebilir veya “Tamamlanma” alt bölümü güncellenir. PLAN_KALAN_ADIMLAR.md’deki “Sonraki / İsteğe bağlı” tablosu da bu dokümanla uyumlu tutulabilir.
