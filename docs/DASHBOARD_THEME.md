# Dashboard tema (light/dark)

Dashboard, `data-theme="light"` | `data-theme="dark"` ile tema değiştirir. Değişkenler `app/globals.css` içinde tanımlı.

## CSS değişkenleri

| Değişken | Açıklama |
|----------|----------|
| `--dash-bg` | Sayfa arka planı |
| `--dash-bg-card` | Kart / panel arka planı |
| `--dash-text` | Ana metin rengi |
| `--dash-text-muted` | İkincil metin |
| `--dash-border` | Kenarlık rengi |
| `--dash-accent` | Vurgu (link, buton) |
| `--dash-accent-bg` | Vurgu arka planı |

## Tutarlılık

- **Yeni bileşenlerde** mümkün olduğunca `var(--dash-*)` kullanın; böylece tema değişiminde renkler tutarlı kalır.
- **Semantik renkler** (başarı=yeşil, hata=kırmızı, uyarı=turuncu) bazı admin sayfalarında sabit hex kullanıyor; ileride `--dash-success`, `--dash-error` vb. eklenebilir.
- Header, error, not-found, privacy sayfaları `var(--dash-*)` ile tema uyumludur.
