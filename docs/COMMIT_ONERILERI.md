# Önerilen commit grupları (bugünkü değişiklikler)

Aşağıdaki sırayla `git add` + `git commit` yapılabilir. Proje kökünden çalıştırın.

---

## 1. Plan dışı: CI, release dokümanları, CHANGELOG

```bash
git add CHANGELOG.md \
  .github/workflows/mobile-e2e.yml \
  docs/RELEASE_CHECKLIST.md \
  docs/TESTING.md \
  docs/PLAN_DISI_ISLER_OZET.md \
  docs/DASHBOARD_KALAN_ISLER.md
git add CONTRIBUTING.md
git commit -m "ci: mobile-e2e Maestro path; docs: pnpm in release/TESTING/CONTRIBUTING; CHANGELOG [Unreleased]"
```

---

## 2. Dashboard UI: Tailwind config, fontlar, layout, bileşenler

```bash
git add dashboard/tailwind.config.ts dashboard/postcss.config.mjs \
  dashboard/app/globals.css dashboard/app/layout.tsx \
  dashboard/components.json dashboard/lib/utils.ts \
  dashboard/app/ThemeToggle.tsx dashboard/app/components/Breadcrumb.tsx
git add dashboard/components/
git commit -m "dashboard: Tailwind v3, token’lar, next/font (Inter, Source Serif 4, JetBrains Mono), layout, ThemeToggle, Breadcrumb"
```

---

## 3. Dashboard: Admin sayfaları Tailwind migrasyonu

```bash
git add dashboard/app/admin/
git commit -m "dashboard: admin sayfaları ve alt sayfalar Tailwind migrasyonu (sessions, status, analytics, tuning-tasks, deployments, feedback, live, users, replay, impact, tuning-report, tuning-metrics)"
```

---

## 4. Dashboard: Erişilebilirlik ve plan dokümanları

```bash
git add docs/DASHBOARD_FAZ6_ACCESSIBILITY.md docs/PLAN_DASHBOARD_UI_MODERN.md
git commit -m "docs: dashboard Faz 6 erişilebilirlik, UI modern plan"
```

---

Not: Build yerelde `cd dashboard && pnpm run build` ile doğrulanmalı (sandbox’ta EPERM alındı).
