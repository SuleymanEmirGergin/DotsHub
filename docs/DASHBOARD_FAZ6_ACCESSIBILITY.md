# Dashboard Faz 6 — Fontlar ve erişilebilirlik

## Yapılanlar

### Fontlar (next/font)

- **Inter** (sans): `layout.tsx` içinde `next/font/google` ile yüklendi; `--font-sans` CSS değişkeni `html` üzerinde set ediliyor.
- **Source Serif 4** (serif): Aynı şekilde yüklendi; `--font-serif`.
- **JetBrains Mono** (mono): Aynı şekilde yüklendi; `--font-mono`.

Tailwind `font-sans`, `font-serif`, `font-mono` bu değişkenlere bağlı (`tailwind.config.ts` → `theme.extend.fontFamily`). Varsayılan gövde metni `font-sans` (Inter) kullanıyor; kod/session id gibi yerlerde `font-mono` kullanılıyor.

### Token doğrulama

- `--font-sans`, `--font-serif`, `--font-mono`: next/font sınıfları `html` üzerinde tanımlıyor; `globals.css` içinde yalnızca fallback (ui-sans-serif vb.) kaldı.
- `body`: `font-sans antialiased` ile Inter uygulanıyor.

---

## Kontrol listesi (erişilebilirlik ve koyu tema)

Manuel kontrol önerileri:

1. **Kontrast (WCAG AA)**
   - Metin: `text-foreground` / `text-muted-foreground` → arka plan `bg-background` / `bg-card` üzerinde yeterli kontrast (en az 4.5:1 normal metin, 3:1 büyük metin).
   - Dark mode: `.dark` token’ları mevcut; sayfaları dark modda açıp başlık, gövde metni ve muted metinleri gözden geçirin.

2. **Odak (focus)**
   - Link ve butonlarda odak halkası: Tailwind `ring` / `ring-offset` veya shadcn bileşenleri kullanılıyorsa görünür odak stili olmalı.
   - Gerekirse `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` ekleyin.

3. **Metin ölçekleme**
   - Sayfa `rem` / token tabanlı olduğu için tarayıcı metin boyutu artırıldığında layout’un bozulmadan ölçeklenmesi gerekir.

4. **Dark tema**
   - ThemeToggle ile light/dark geçişi; `document.documentElement.classList.toggle("dark", …)` ile token’lar güncelleniyor.
   - Admin sayfalardaki durum/severity renkleri (yeşil, kırmızı, amber) dark varyantlarla (`dark:bg-*`, `dark:text-*`) tanımlı; dark modda kontrastı kontrol edin.

Bu liste her release öncesi veya büyük UI değişikliği sonrası tekrarlanabilir.
