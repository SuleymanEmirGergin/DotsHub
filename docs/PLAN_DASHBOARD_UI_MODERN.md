# Plan: Dashboard UI — Tailwind v3 ve modern minimal tema

**Amaç:** Dashboard görünümünü Tailwind v3 ve modern bir bileşen seti (shadcn/ui + modern-minimal tema) ile güncellemek. Mevcut CSS değişkenleri ve inline stiller yerine tasarım token’ları ve utility-first yaklaşım kullanılacak.

**Kapsam:** `dashboard/` (Next.js). Mobil uygulama (Expo) bu planda yer almaz.

---

## 1. Mevcut durum

- **Styling:** `app/globals.css` içinde `--dash-bg`, `--dash-text`, `--dash-border` vb. custom properties; bileşenlerde yoğun inline `style={{ ... }}` kullanımı.
- **Tailwind:** Projede Tailwind yok.
- **Tema:** `data-theme="light" | "dark"` ile ThemeToggle; renkler CSS değişkenleriyle veriliyor.

---

## 2. Hedef mimari

| Katman | Araç | Açıklama |
|--------|------|----------|
| Tasarım token’ları | CSS variables (HSL) | `:root` ve `.dark` ile light/dark; Tailwind config bu değişkenlere bağlanır. |
| Utility / layout | Tailwind CSS v3 | `bg-background`, `text-foreground`, `border-border`, `rounded-lg` vb. |
| Bileşenler | shadcn/ui + modern-minimal | Button, Card, Table, Breadcrumb vb. tutarlı ve erişilebilir. |
| Tema değişimi | `class` stratejisi | `darkMode: ["class"]`; `<html className={dark ? "dark" : ""}>`. |

---

## 3. Verdiğiniz yapılandırma (referans)

### 3.1 `index.css` — CSS değişkenleri (light + dark)

Light ve dark için HSL tabanlı token’lar. Özet:

- **Renkler:** `--background`, `--foreground`, `--card`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--popover`, `--sidebar*`, `--chart-1..5`.
- **Tipografi:** `--font-sans` (Inter), `--font-serif` (Source Serif 4), `--font-mono` (JetBrains Mono).
- **Radius:** `--radius` (0.375rem).
- **Gölge:** `--shadow-2xs` … `--shadow-2xl`.

Dark tema için `.dark` sınıfı ile aynı isimli değişkenlerin koyu değerleri tanımlanır.

*(Tam içerik mesajınızda yer alan `:root` ve `.dark` bloklarıdır; burada tekrarlanmadı.)*

### 3.2 `tailwind.config.ts`

- `darkMode: ["class"]`
- `theme.extend`: `colors` (border, input, ring, background, foreground, primary, secondary, destructive, muted, accent, popover, card, sidebar, chart), `borderRadius` (xl, lg, md, sm), `fontFamily` (sans, serif, mono).
- Renkler `hsl(var(--primary))` gibi CSS değişkenlerine referans verir.

*(Tam içerik mesajınızda verilen `module.exports` bloğudur.)*

### 3.3 shadcn tema

```bash
pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/modern-minimal.json
```

Bu komut modern-minimal temasını projeye ekler (shadcn kurulumu varsa tema bileşenleri ve stilleri gelir).

---

## 4. Uygulama fazları

### Faz 1: Tailwind v3 + PostCSS kurulumu

1. Dashboard’da Tailwind v3 ve bağımlılıklarını yükle:
   ```bash
   cd dashboard
   pnpm add -D tailwindcss@3 postcss autoprefixer
   npx tailwindcss init -p
   ```
2. `tailwind.config.ts` dosyasını oluştur; içeriği verdiğiniz `tailwind.config.ts` ile değiştir (theme.extend, darkMode: ["class"]).
3. `postcss.config.mjs` (veya `.config.cjs`) içinde `tailwindcss` ve `autoprefixer` kullanıldığından emin ol.

### Faz 2: Global CSS ve tasarım token’ları

1. `app/globals.css` dosyasını verdiğiniz `index.css` içeriği ile güncelle:
   - `:root` ve `.dark` bloklarını ekle (veya mevcut `--dash-*` değişkenlerini yeni token’lara eşleyerek geçiş yap).
2. Tailwind direktiflerini ekle:
   ```css
   @tailwind base;
   @tailwind components;
   @tailwind utilities;
   ```
3. Mevcut `body` ve `.dash-panel` kurallarını yeni token’lara göre uyarlayın veya Tailwind sınıflarına taşıyın (`bg-background`, `text-foreground` vb.).
4. Dark mode: Root layout’ta tema sınıfının `<html className={theme}>` gibi verilmesi; ThemeToggle’ın `document.documentElement.classList.toggle("dark", isDark)` ile çalışması.

### Faz 3: shadcn/ui ve modern-minimal tema

**Hazır:** `components.json`, `lib/utils.ts` (cn) ve `components/ui/` oluşturuldu. Tailwind + token’lar Faz 1–2’de uygulandı.

1. **İsteğe bağlı — shadcn init (zaten yapılandırıldıysa atlayın):**
   ```bash
   cd dashboard
   pnpm dlx shadcn@latest init
   ```
   - Base color: **Neutral** seçin; CSS variables: Yes.
2. **Modern-minimal temayı ekleyin (etkileşimli olabilir):**
   ```bash
   cd dashboard
   pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/modern-minimal.json
   ```
3. Oluşan bileşen ve stilleri `components/ui/` ve globals ile uyumlu kontrol edin; gerekirse `globals.css` ile çakışan kısımları token’lara göre düzenleyin.

### Faz 4: Layout ve ortak bileşenlere geçiş

1. **Root layout (`app/layout.tsx`):**
   - `html` ve `body` için Tailwind sınıfları: `bg-background`, `text-foreground`, `font-sans`.
   - Header’daki link ve butonları shadcn `Button` veya benzeri ile değiştir (isteğe bağlı).
2. **ThemeToggle:**
   - `class` tabanlı dark mode’a göre güncelle; `document.documentElement.classList.add("dark")` / `remove("dark")`.
3. **Breadcrumb:**
   - Mevcut `app/components/Breadcrumb.tsx`’i shadcn Breadcrumb ile değiştir veya stilleri Tailwind + token’larla yeniden yaz.

### Faz 5: Admin sayfalarının migrasyonu

1. **Öncelik sırası önerisi:** layout → sessions → status → analytics → tuning-tasks → deployments → feedback → live → users → diğerleri.
2. Her sayfada:
   - Inline `style={{ ... }}` kullanımlarını `className` ve Tailwind utility’lere çevir.
   - Kart / panel: `bg-card`, `border-border`, `rounded-lg`, `shadow`.
   - Tablo: shadcn Table veya Tailwind tablo sınıfları.
   - Buton / link: shadcn Button, Link stilleri.
3. Eski `--dash-*` referansları kaldırılacaksa, önce yeni token’lara eşleme tablosu yazılabilir (örn. `--dash-bg` → `bg-background`).

### Faz 6: Font ve son dokunuşlar

1. `layout.tsx` veya `globals.css` ile Inter, Source Serif 4, JetBrains Mono fontlarını yükleyin (Google Fonts veya yerel).
2. `--font-sans`, `--font-serif`, `--font-mono` değişkenlerinin uygulandığını doğrulayın.
3. Erişilebilirlik ve koyu tema kontrastını kontrol edin.

---

## 5. Dosya etkileri (özet)

| Dosya / klasör | Değişiklik |
|----------------|------------|
| `dashboard/package.json` | tailwindcss, postcss, autoprefixer; shadcn ile gelen bağımlılıklar |
| `dashboard/tailwind.config.ts` | Yeni oluşturulur (verdiğiniz config) |
| `dashboard/postcss.config.mjs` | Yeni oluşturulur veya güncellenir |
| `dashboard/app/globals.css` | index.css içeriği + @tailwind; eski --dash-* kaldırılabilir veya eşlenir |
| `dashboard/app/layout.tsx` | className’ler, theme class’ı, font |
| `dashboard/app/components/ThemeToggle.tsx` | class tabanlı dark mode |
| `dashboard/app/components/Breadcrumb.tsx` | shadcn Breadcrumb veya Tailwind stilleri |
| `dashboard/app/admin/**/*.tsx` | Inline style → Tailwind + shadcn bileşenleri |
| `dashboard/components/ui/*` | shadcn ile eklenecek bileşenler |

---

## 6. Eşleme: Eski → Yeni (geçiş rehberi)

| Eski (--dash-*) | Yeni (Tailwind / token) |
|-----------------|--------------------------|
| `var(--dash-bg)` | `bg-background` |
| `var(--dash-bg-card)` | `bg-card` |
| `var(--dash-text)` | `text-foreground` |
| `var(--dash-text-muted)` | `text-muted-foreground` |
| `var(--dash-border)` | `border-border` |
| `var(--dash-accent)` | `text-primary` / `bg-primary` |
| `var(--dash-accent-bg)` | `bg-accent` |

---

## 7. Notlar

- **Tailwind v3:** v4 değil, v3 kullanılacak (isteğiniz ve mevcut shadcn/tweakcn uyumluluğu için).
- **Mobil:** Bu plan yalnızca dashboard içindir; mobil uygulama (Expo) farklı stil sistemi kullanır.
- **İlerleme:** Faz 1–3 tamamlandıktan sonra sayfa sayfa (Faz 5) geçiş yapılabilir; aynı anda tüm inline stilleri kaldırmak zorunlu değildir.
- **Test:** `pnpm run build` ve `pnpm run lint` her faz sonrası çalıştırılmalı; görsel olarak light/dark ve ana sayfalar kontrol edilmeli.

---

## 8. Başlangıç komutları (özet)

```bash
cd dashboard
pnpm add -D tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
# tailwind.config.ts içeriğini yapıştır
# app/globals.css'i index.css + @tailwind ile güncelle

pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add https://tweakcn.com/r/themes/modern-minimal.json
```

Bu plan dokümanı, verdiğiniz `index.css`, `tailwind.config.ts` ve `pnpm dlx shadcn@latest add ...` komutuna göre hazırlandı. Uygulama sırasında bir adımı otomatikleştirmek veya belirli sayfaları önceliklendirmek isterseniz planda ilgili faza madde ekleyebilirsiniz.

---

## Ek A: Örnek `index.css` (tam token seti)

Aşağıdaki içerik `dashboard/app/globals.css` için referans olarak kullanılabilir. Tailwind direktifleri (`@tailwind base;` vb.) bu dosyada en üste eklenmelidir.

```css
:root {
  --background: 0 0% 100%;
  --foreground: 0 0% 20%;
  --card: 0 0% 100%;
  --card-foreground: 0 0% 20%;
  --popover: 0 0% 100%;
  --popover-foreground: 0 0% 20%;
  --primary: 217.2193 91.2195% 59.8039%;
  --primary-foreground: 0 0% 100%;
  --secondary: 220 14.2857% 95.8824%;
  --secondary-foreground: 215 13.7931% 34.1176%;
  --muted: 210 20% 98.0392%;
  --muted-foreground: 220 8.9362% 46.0784%;
  --accent: 204 93.75% 93.7255%;
  --accent-foreground: 224.4444 64.2857% 32.9412%;
  --destructive: 0 84.2365% 60.1961%;
  --destructive-foreground: 0 0% 100%;
  --border: 220 13.0435% 90.9804%;
  --input: 220 13.0435% 90.9804%;
  --ring: 217.2193 91.2195% 59.8039%;
  --chart-1: 217.2193 91.2195% 59.8039%;
  --chart-2: 221.2121 83.1933% 53.3333%;
  --chart-3: 224.2781 76.3265% 48.0392%;
  --chart-4: 225.9310 70.7317% 40.1961%;
  --chart-5: 224.4444 64.2857% 32.9412%;
  --sidebar: 210 20% 98.0392%;
  --sidebar-foreground: 0 0% 20%;
  --sidebar-primary: 217.2193 91.2195% 59.8039%;
  --sidebar-primary-foreground: 0 0% 100%;
  --sidebar-accent: 204 93.75% 93.7255%;
  --sidebar-accent-foreground: 224.4444 64.2857% 32.9412%;
  --sidebar-border: 220 13.0435% 90.9804%;
  --sidebar-ring: 217.2193 91.2195% 59.8039%;
  --font-sans: Inter, sans-serif;
  --font-serif: Source Serif 4, serif;
  --font-mono: JetBrains Mono, monospace;
  --radius: 0.375rem;
}

.dark {
  --background: 0 0% 9.0196%;
  --foreground: 0 0% 89.8039%;
  --card: 0 0% 14.9020%;
  --card-foreground: 0 0% 89.8039%;
  --popover: 0 0% 14.9020%;
  --popover-foreground: 0 0% 89.8039%;
  --primary: 217.2193 91.2195% 59.8039%;
  --primary-foreground: 0 0% 100%;
  --secondary: 0 0% 14.9020%;
  --secondary-foreground: 0 0% 89.8039%;
  --muted: 0 0% 12.1569%;
  --muted-foreground: 0 0% 63.9216%;
  --accent: 224.4444 64.2857% 32.9412%;
  --accent-foreground: 213.3333 96.9231% 87.2549%;
  --destructive: 0 84.2365% 60.1961%;
  --destructive-foreground: 0 0% 100%;
  --border: 0 0% 25.0980%;
  --input: 0 0% 25.0980%;
  --ring: 217.2193 91.2195% 59.8039%;
  --chart-1: 213.1169 93.9024% 67.8431%;
  --chart-2: 217.2193 91.2195% 59.8039%;
  --chart-3: 221.2121 83.1933% 53.3333%;
  --chart-4: 224.2781 76.3265% 48.0392%;
  --chart-5: 225.9310 70.7317% 40.1961%;
  --sidebar: 0 0% 9.0196%;
  --sidebar-foreground: 0 0% 89.8039%;
  --sidebar-primary: 217.2193 91.2195% 59.8039%;
  --sidebar-primary-foreground: 0 0% 100%;
  --sidebar-accent: 224.4444 64.2857% 32.9412%;
  --sidebar-accent-foreground: 213.3333 96.9231% 87.2549%;
  --sidebar-border: 0 0% 25.0980%;
  --sidebar-ring: 217.2193 91.2195% 59.8039%;
}
```

---

## Ek B: Örnek `tailwind.config.ts`

```ts
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        chart: {
          1: "hsl(var(--chart-1))",
          2: "hsl(var(--chart-2))",
          3: "hsl(var(--chart-3))",
          4: "hsl(var(--chart-4))",
          5: "hsl(var(--chart-5))",
        },
      },
      borderRadius: {
        xl: "calc(var(--radius) + 4px)",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        serif: ["var(--font-serif)"],
        mono: ["var(--font-mono)"],
      },
    },
  },
};
```
