# Yapılabilecekler Listesi

Proje durumuna göre önerilen geliştirmeler. Öncelik sırası yok; ihtiyaca göre seçilebilir.

---

## Mobil (Expo)

- **Türkçe karakter düzeltmeleri** — Bazı placeholder/label’larda Türkçe karakter eksik (örn. "Semptomlarini" → "Semptomlarını", "Cevabin" → "Cevabın", "Degerlendiriliyor" → "Değerlendiriliyor").
- **Sonuç ekranında PDF paylaşımı** — "Özeti paylaş" metin paylaşıyor; `expo-print` ile PDF oluşturup `expo-sharing` ile paylaşım eklenebilir.
- **Mobilde GET /v1/facilities kullanımı** — Sonuç ekranında "Daha fazla tesis göster" ile ayrı facility endpoint’inden ek liste çekilebilir.
- **Onboarding / izin açıklamaları** — Konum izni ve (varsa) bildirim için kısa açıklama ekranları.
- **Erişilebilirlik (a11y)** — `accessibilityLabel`, `accessibilityHint`, büyük dokunma alanları, ekran okuyucu uyumu.
- **Splash / loading ekranı** — Uygulama açılışında marka ve yükleme göstergesi.
- **Bildirimler (push)** — Same-day / acil senaryolarda (opsiyonel) hatırlatma; politika ve izin netleştirilmeli.

---

## Backend (FastAPI)

- **Rate limit: Redis ile** — Şu an in-memory; çok instance’da Redis tabanlı rate limit.
- **Structured logging** — JSON log + request_id; log aggregation için uyum.
- **OpenAPI dokümantasyonu** — `docs/openapi_orchestrator.yaml` ile senkron; `GET /v1/facilities` ve diğer yeni endpoint’lerin eklenmesi.
- **Health detayı** — `/health` içinde Supabase / dependency durumu (opsiyonel).
- **i18n hazırlığı** — Soru/cevap ve sabit metinlerin key’lere taşınması; locale’e göre metin seçimi (şu an `tr-TR` tek).
- **PII / audit** — Log’larda PII’ın tutarlı maskelemesi ve audit event’lerinin net formatı.

---

## Dashboard (Next.js)

- ~~**Login sayfasında tema**~~ — ✅ Dark mode (var(--dash-*)) eklendi.
- **Diğer admin sayfalarında tema** — Analytics, tuning-report, sessions-v5, deployments vb. sayfalarda CSS değişkenleri.
- ~~**Sistem durumu sayfasında otomatik yenileme**~~ — ✅ 30 sn aralıkla yenileme eklendi.
- **Breadcrumb / navigasyon** — Admin alt sayfalarında "Sessions > Session detail" gibi yol.
- **Tablo sıralama / filtre** — Sessions ve tuning-tasks tablolarında sütun bazlı sıralama ve ek filtreler.
- **Export** — Sessions veya tuning task listesini CSV/Excel olarak indirme.

---

## Kalite ve operasyon

- **Mobil birim testleri** — Kritik yardımcılar (deviceId, location, envelopeRouter) ve store için Jest/React Native Testing Library.
- **Dashboard birim testleri** — Önemli bileşenler ve API route’lar için test.
- **E2E (Playwright)** — Dashboard: login → sessions listesi; isteğe bağlı mobil (Detox/Maestro).
- **CI’da backend testleri** — Mevcut workflow’lara `test_triage_turn_e2e` ve diğer testlerin eklenmesi.
- **Dependency güncellemeleri** — `npm audit` / `pip-audit` ve düzenli minor/patch güncellemeleri.

---

## Güvenlik ve uyumluluk

- **Admin API: rate limit** — `/v1/admin/*` için ayrı (daha sıkı) rate limit veya IP kısıtı.
- **CORS daraltma** — Production’da `allow_origins` listesinin net tanımlanması.
- **Secrets taraması** — CI’da .env veya kod içi secret kontrolü (örn. gitleaks, trufflehog).
- **HTTPS / güvenli header’lar** — Production’da HSTS, X-Content-Type-Options vb.

---

## Özellik (ürün)

- **Çoklu dil (i18n)** — Backend’de locale; mobil ve dashboard’da dil seçimi ve metin key’leri.
- **Anonim istatistik** — Triaj sonuçlarının toplu (anonim) istatistiği; dashboard’da basit grafikler.
- **Tesis detayı** — Facility listesinde harita linki (Google Maps / Apple Maps / OSM) veya basit harita önizlemesi.
- **Oturum özeti e‑posta** — Kullanıcı e‑posta verirse "Sonuç özeti" e‑posta ile gönderilmesi (Supabase Edge Function veya backend job).

---

## Dokümantasyon ve onboarding

- **README güncellemesi** — Yeni endpoint’ler (facilities, rate limit header’ları), env değişkenleri, kurulum adımları.
- **CONTRIBUTING / geliştirici rehberi** — Branch stratejisi, test çalıştırma, mock’lar.
- **API örnekleri** — `curl` veya Postman koleksiyonu ile `/v1/triage/turn` ve `/v1/facilities` örnekleri.
- **Changelog** — Önemli sürümler için CHANGELOG.md.

---

## Kısa özet (madde başına tek satır)

| # | Kategori   | Öneri |
|---|------------|--------|
| 1 | Mobil      | Türkçe karakter düzeltmeleri (placeholder/label) |
| 2 | Mobil      | Sonuç özeti PDF paylaşımı (expo-print + sharing) |
| 3 | Mobil      | Sonuç ekranında GET /v1/facilities ile "Daha fazla tesis" |
| 4 | Mobil      | Onboarding / konum-bildirim izin açıklamaları |
| 5 | Mobil      | Erişilebilirlik (accessibilityLabel, hint, alanlar) |
| 6 | Mobil      | Splash / loading ekranı |
| 7 | Mobil      | (Opsiyonel) Push bildirimleri politikası ve implementasyonu |
| 8 | Backend    | Rate limit için Redis kullanımı |
| 9 | Backend    | Structured logging (JSON + request_id) |
| 10 | Backend   | OpenAPI güncellemesi (facilities, yeni alanlar) |
| 11 | Backend   | /health’e dependency (Supabase) bilgisi |
| 12 | Backend   | i18n hazırlığı (metin key’leri, locale) |
| 13 | Dashboard | Login ve tüm admin sayfalarında dark mode (CSS var) |
| 14 | Dashboard | Sistem durumu sayfasında otomatik yenileme |
| 15 | Dashboard | Breadcrumb / net navigasyon |
| 16 | Dashboard | Tablolarda sıralama ve filtre |
| 17 | Dashboard | Sessions/tuning listesi CSV/Excel export |
| 18 | Kalite    | Mobil birim testleri (Jest) |
| 19 | Kalite    | Dashboard birim testleri |
| 20 | Kalite    | Playwright ile dashboard E2E |
| 21 | Kalite    | CI’da tüm backend testlerinin çalıştırılması |
| 22 | Güvenlik  | Admin API rate limit / IP kısıtı |
| 23 | Güvenlik  | Production CORS daraltma |
| 24 | Güvenlik  | CI’da secret taraması |
| 25 | Ürün      | Çoklu dil (i18n) |
| 26 | Ürün      | Anonim triaj istatistikleri ve grafikler |
| 27 | Ürün      | Tesis için harita linki / önizleme |
| 28 | Ürün      | (Opsiyonel) Sonuç özeti e‑posta gönderimi |
| 29 | Dokümantasyon | README ve env dokümantasyonu güncellemesi |
| 30 | Dokümantasyon | CONTRIBUTING / geliştirici rehberi |
| 31 | Dokümantasyon | API örnekleri (curl/Postman) |
| 32 | Dokümantasyon | CHANGELOG.md |

---

*Son güncelleme: Planlanan özellikler (retry, paylaşım, rate limit UI, dark mode, status sayfası, E2E, facilities endpoint) uygulandıktan sonra derlendi.*
