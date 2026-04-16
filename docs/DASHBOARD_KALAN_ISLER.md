# Dashboard — Kalan işler (manuel)

Admin alt sayfaların Tailwind migrasyonu tamamlandı. Aşağıdakiler isteğe bağlı veya manuel.

## 1. shadcn modern-minimal tema (isteğe bağlı)

Tema bileşenlerini eklemek için (dashboard dizininde):

```bash
cd dashboard
pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/modern-minimal.json
```

Etkileşimli olabilir; gerekirse base color vb. seçin. Daha önce `components.json` ve `lib/utils.ts` hazırlandığı için komut çalışacaktır.

## 2. Build ve görsel kontrol

- `cd dashboard && pnpm run build`
- Light ve dark temada ana sayfaları ve admin sayfalarını tarayıcıda kontrol edin.

## 3. Erişilebilirlik kontrastı

`docs/DASHBOARD_FAZ6_ACCESSIBILITY.md` içindeki kontrast, odak ve dark tema maddelerini gerektiğinde uygulayın.

---

**Tamamlanan:** Tüm admin sayfaları (ana + alt) Tailwind + token kullanıyor; Faz 1–6 (fontlar dahil) uygulandı.
