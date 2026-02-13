# Changelog

Tüm önemli değişiklikler bu dosyada listelenir.

## [Unreleased]

- CONTRIBUTING.md ve docs/API_EXAMPLES.md eklendi.
- CI’da backend unit/E2E testleri açık adım olarak çalışıyor.
- Admin API için ayrı rate limit (IP bazlı, varsayılan 60/dk).
- README’de API & Environment bölümü (env değişkenleri, endpoint’ler).

## [4.0.0] — Unified triage turn

- `POST /v1/triage/turn` tek endpoint ile oturum başlatma, cevap verme ve sonuç.
- Zarf tipleri: `EMERGENCY`, `SAME_DAY`, `QUESTION`, `RESULT`, `ERROR`.
- Rate limit: triaj ve feedback için X-RateLimit-* header’ları; Redis opsiyonel.
- `GET /v1/facilities` — tesis keşfi (specialty, city, lat/lon, limit).
- `/health` — Supabase erişim bilgisi.
- Structured logging (JSON + request_id), X-Request-ID response header.
- i18n hazırlığı (app/core/i18n.py), PII maskeleme (app/core/pii.py).
- Dashboard: dark mode, breadcrumb, tablo sıralama, CSV export, sistem durumu otomatik yenileme.
- Mobil: splash ekranı, PDF paylaşımı, daha fazla tesis, erişilebilirlik, konum izni açıklaması.

---

Format [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). Sürümler [Semantic Versioning](https://semver.org/spec/v2.0.0.html) ile uyumludur.
