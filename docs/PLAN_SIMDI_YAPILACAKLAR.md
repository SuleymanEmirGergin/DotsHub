# Plan: Şimdi yapılacaklar (tek tek)

Bugün tamamlanan işlerin commit’lenmesi ve doküman güncellemeleri. Sırayla uygulanacak.

---

## Adım 1: Commit — Dashboard (Analytics + E2E)

- **Dosyalar:** `dashboard/app/admin/analytics/page.tsx`, `dashboard/e2e/admin.spec.ts`
- **İçerik:** Analytics sayfasında shadcn Card/Button; E2E’de status sayfası “service card” senaryosu.
- **Commit mesajı:** `dashboard: analytics shadcn Card/Button, E2E status service card senaryosu`

---

## Adım 2: Commit — Backend (health testi)

- **Dosyalar:** `backend/tests/test_health.py`
- **İçerik:** `GET /health` için 200 ve `status: ok` testi.
- **Commit mesajı:** `backend: GET /health icin test_health.py`

---

## Adım 3: Commit — Docs (TESTING, DEPENDENCY_AUDIT, CHECKLIST)

- **Dosyalar:** `docs/TESTING.md`, `docs/DEPENDENCY_AUDIT.md`, `docs/RELEASE_CHECKLIST.md`
- **İçerik:** TESTING.md Maestro yerel + test_health; yeni DEPENDENCY_AUDIT.md; RELEASE_CHECKLIST’e referans.
- **Commit mesajı:** `docs: TESTING Maestro + test_health, DEPENDENCY_AUDIT, RELEASE_CHECKLIST ref`

---

## Adım 4: PLAN_BIRAZ_DAHA_ZAMAN_ALABILECEKLER.md güncelle

- **Dosya:** `docs/PLAN_BIRAZ_DAHA_ZAMAN_ALABILECEKLER.md`
- **İçerik:** Madde 1 (Playwright E2E) ve Madde 3 (shadcn tema) için “Tamamlandı” notu ekle.

---

## Adım 5: README / CONTRIBUTING kontrol

- **Dosyalar:** `README.md`, `CONTRIBUTING.md`
- **İçerik:** Dashboard komutları (pnpm, test:routes, test:e2e) ve test dokümantasyonu güncel mi kontrol et; gerekirse tek cümle ekle veya düzelt.

---

## Sıra özeti

| # | Adım | Durum |
|---|------|--------|
| 1 | Commit dashboard (analytics + E2E) | Tamamlandı |
| 2 | Commit backend (test_health) | Tamamlandı |
| 3 | Commit docs | Tamamlandı |
| 4 | PLAN doc tamamlandı notları | Tamamlandı |
| 5 | README/CONTRIBUTING kontrol | Tamamlandı |

Tamamlandıkça bu tabloda “Tamamlandı” işaretlenebilir.
