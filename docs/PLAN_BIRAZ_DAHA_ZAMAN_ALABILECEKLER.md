# Plan: Biraz daha zaman alabilecek işler

Bu doküman, kısa sürede bitirilebilecek işler tamamlandıktan sonra yapılabilecek üç işin sırasını ve adımlarını tanımlar.

---

## 1. Playwright E2E (Dashboard)

**Amaç:** Admin akışının tarayıcıda otomatik test edilmesi; CI veya yerel “yeşil” kontrolü.

**Ön koşul:** Dashboard build yerelde geçiyor olmalı (`cd dashboard && pnpm run build`).

| Adım | Ne yapılır | Tahmini |
|------|-------------|--------|
| 1.1 | `cd dashboard && pnpm run test:e2e` çalıştır (headless). Hata varsa e2e/admin.spec.ts veya test ortamını (NEXT_PUBLIC_*, ADMIN_API_KEY) düzelt. | 10–20 dk |
| 1.2 | İsteğe bağlı: CI’da E2E adımı (örn. `.github/workflows/dashboard-quality.yml` veya ayrı workflow). Playwright’ın CI’da kurulumu (install browsers) ve env (secrets) gerekir. | 15–30 dk |
| 1.3 | README veya TESTING.md’de E2E komutunu ve “CI’da çalışıyor mu?” notunu güncelle. | 5 dk |

**Çıktı:** Yerelde ve (isteğe bağlı) CI’da `pnpm run test:e2e` yeşil; dokümantasyon güncel.

**Tamamlandı:** 2025-02-19 (config pnpm, port 3002, CI dashboard-tests/dashboard-quality, TESTING.md).

---

## 2. Release hazırlığı (CHANGELOG + checklist)

**Amaç:** [Unreleased] dolu; yeni sürüm (örn. 4.6.0) çıkarmak için checklist’i uygulamak.

| Adım | Ne yapılır | Tahmini |
|------|-------------|--------|
| 2.1 | RELEASE_CHECKLIST.md “0. Sürüm öncesi” maddelerini uygula: backend regression, dashboard test:routes + test:i18n-contract, isteğe bağlı test:e2e; pnpm audit (dashboard, mobile), pip list --outdated (backend); DEPENDENCY_UPDATES ile karşılaştır. | 15–20 dk |
| 2.2 | CHANGELOG.md: [Unreleased] altındaki maddeleri `## [4.6.0] — YYYY-MM-DD` başlığına taşı; [Unreleased] altında sadece `- (Yeni değişiklikler buraya.)` kalsın. | 5 dk |
| 2.3 | Tag: `git tag v4.6.0` ve `git push origin v4.6.0`. | 2 dk |
| 2.4 | GitHub/GitLab release sayfasında yeni release oluştur; tag seç, CHANGELOG’daki maddeleri açıklamaya yapıştır. | 5 dk |
| 2.5 | İsteğe bağlı: POST_RELEASE_MANUEL_ADIMLAR.md (branch protection, production kontrolü). | 10–15 dk |

**Çıktı:** Yeni sürüm tag’i ve release sayfası; checklist işaretlenmiş.

---

## 3. shadcn modern-minimal tema (Dashboard)

**Amaç:** Dashboard’a modern-minimal tema bileşenlerini eklemek (buton, kart, tablo vb. tutarlı görünsün).

**Ön koşul:** Dashboard’da Tailwind + `components.json` + `lib/utils.ts` hazır (Faz 1–3 tamamlandı).

| Adım | Ne yapılır | Tahmini |
|------|-------------|--------|
| 3.1 | `cd dashboard && pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/modern-minimal.json` çalıştır. Etkileşimli sorularda base color vb. seç (veya varsayılan). | 5–10 dk |
| 3.2 | Oluşan bileşenleri ve stilleri kontrol et; `globals.css` veya mevcut token’larla çakışma varsa düzelt. | 10–15 dk |
| 3.3 | İsteğe bağlı: Bir admin sayfasında shadcn Button/Card kullanarak örnek değişiklik yap; görsel olarak light/dark kontrol et. | 10–20 dk |

**Çıktı:** `dashboard/components/ui/` altında tema bileşenleri; isteğe bağlı bir sayfada kullanım örneği.

**Tamamlandı:** 2025-02-19 (Tailwind var(--...), Button/Card, status + analytics ornekleri).

---

## Önerilen sıra

1. **Playwright E2E** — Testler yeşil olsun; release öncesi de faydalı.
2. **Release hazırlığı** — Sürüm çıkaracaksan CHANGELOG + tag + release.
3. **shadcn tema** — Görsel tutarlılık; release’ten bağımsız, isteğe bağlı.

İstersen her madde tamamlandıkça bu dokümanda “Tamamlandı: YYYY-MM-DD” notu eklenebilir.
