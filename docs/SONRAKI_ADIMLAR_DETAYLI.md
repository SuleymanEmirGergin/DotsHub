# Sonraki adımlar – Detaylı kontrol listesi

Her konu alt adımlara bölünmüştür. Sırayla veya ihtiyaca göre ilerleyebilirsiniz.

---

## Son durum ve sonraki madde planı

**Tamamlanan (Arapça RTL):**
- `I18nProvider`: `locale === "ar"` iken root `View` için `direction: "rtl"` uygulandı.
- `useI18n()` artık `isRTL` döndürüyor; `RTL_TEXT_STYLE` (writingDirection + textAlign) export edildi.
- Dil ekranı, IntroScreen ve ResultScreen’de metinler Arapça seçiliyken RTL stil ile hizalanıyor.

**Sonraki madde planı: 2.3 Özet e-posta ve metin indirme**

| Sıra | Ne yapılacak | Nerede / API |
|------|----------------|--------------|
| 1 | Sonuç ekranına “Özeti e-postaya gönder” bölümü | `ResultScreen`: TextInput (e-posta) + buton |
| 2 | E-posta gönderme | `POST /v1/triage/send-summary` — body: `{ session_id, email, locale }` |
| 3 | “Metni indir” butonu | `ResultScreen`: buton tıklanınca `POST /v1/triage/export-summary` |
| 4 | Export-summary isteği | Body: `{ payload: resultPayload, locale }`; response: text/plain → dosya kaydet veya Share |
| 5 | API client | `mobile`: `sendSummaryEmail(sessionId, email, locale)`, `exportSummary(payload, locale)` fonksiyonları |
| 6 | Hata / yükleme | Butonlarda loading, hata mesajı (Alert veya inline) |

**Veri kaynağı:** `sessionId` ve `resultPayload` (RESULT envelope) zaten `useTriageStore` içinde mevcut.

---

## Konu 1: Entegrasyonlar (Backend)

### 1.1 main.py – Router’lar

| Adım | Durum | Açıklama |
|------|--------|----------|
| summary_email router | ✅ | `app.include_router(summary_email_router, prefix="/v1")` — mevcut |
| SecurityHeadersMiddleware | ✅ | CORS’tan sonra ekli |
| app.state.app_env | ✅ | Lifespan içinde `app.state.app_env = settings.APP_ENV` |
| triage, feedback, facilities, session, message, admin | ✅ | Tüm router’lar prefix `/v1` ile ekli |

**Sonuç:** main.py entegrasyonları tamam.

### 1.2 summary_email – Session tablosu

| Adım | Durum | Açıklama |
|------|--------|----------|
| Tablo fallback | ✅ | `_get_session_by_id`: önce `triage_sessions_v5`, yoksa `triage_sessions` denenir |
| get_supabase | ✅ | `app.supabase_client.get_supabase` kullanılıyor |

**Not:** Supabase’de hangi tabloda oturum tutulduğuna göre ilk eşleşen tablo kullanılır.

### 1.3 Yapılacak (opsiyonel)

- `POST /v1/triage/send-summary` ve `POST /v1/triage/export-summary` için rate limit (Konu 4’te ele alınabilir).

---

## Konu 2: Mobil (Expo)

### 2.1 i18n kullanımı

| # | Adım | Dosya / Yer | Açıklama |
|---|------|-------------|----------|
| 1 | I18nProvider sarmalama | `app/_layout.tsx` | `<I18nProvider>` ile root layout sarmalayın |
| 2 | useI18n hook | Ekranlar | `const { t, locale, setLocale } = useI18n()` |
| 3 | Metin çevirileri | `mobile/i18n/tr.json`, `en.json` | `result.openOnMap`, `result.recommendedSpecialty`, `triage.symptomsPlaceholder` vb. |
| 4 | Varsayılan dil | `expo-localization` | `getLocales()` ile cihaz diline göre ilk locale |

**Kod örneği (_layout.tsx):**
```tsx
import { I18nProvider } from '@/i18n/I18nProvider';
export default function RootLayout() {
  return (
    <I18nProvider>
      <Stack />
    </I18nProvider>
  );
}
```

**Kod örneği (ekran):**
```tsx
const { t } = useI18n();
<Text>{t("result.openOnMap")}</Text>
```

### 2.2 Dil seçimi

| # | Adım | Açıklama |
|---|------|----------|
| 1 | Ayarlar ekranı | "Dil" seçeneği: Türkçe / English |
| 2 | Tercih saklama | AsyncStorage veya context ile `locale` (tr / en) |
| 3 | İlk açılış | `expo-localization.getLocales()[0].languageCode` → tr/en eşle, yoksa tr |

### 2.3 Özet e-posta ve metin indirme (Sonuç ekranı)

| # | Adım | API | Açıklama |
|---|------|-----|----------|
| 1 | "Özeti e-postaya gönder" | `POST /v1/triage/send-summary` | Body: `{ session_id, email, locale }` |
| 2 | E-posta alanı | — | Sonuç ekranında TextInput + buton |
| 3 | "Metni indir" | `POST /v1/triage/export-summary` | Body: `{ payload: resultPayload, locale }` → response text/plain; dosya olarak kaydet veya paylaş |

**Not:** `session_id` ve `resultPayload` triage turn akışından (RESULT envelope) gelir.

### 2.4 Push bildirimleri

| # | Adım | Açıklama |
|---|------|----------|
| 1 | İzin | `expo-notifications.requestPermissionsAsync()` — ayarlar veya ilk sonuç sonrası |
| 2 | Token | `getExpoPushTokenAsync()` (Expo Go’da sınırlı; development build gerekebilir) |
| 3 | Backend’e gönderme | Token’ı session veya kullanıcı ile backend’e POST |
| 4 | Politika | `docs/PUSH_NOTIFICATIONS_POLICY.md` — ne zaman bildirim gönderileceği |

### 2.5 Error boundary

| # | Adım | Açıklama |
|---|------|----------|
| 1 | React Error Boundary | Root’a veya ekran gruplarına `<ErrorBoundary fallback={...}>` |
| 2 | Fallback UI | "Bir hata oluştu. Yeniden dene." + isteğe bağlı raporlama |

### 2.6 Offline / retry

| # | Adım | Açıklama |
|---|------|----------|
| 1 | Ağ hatası tespiti | İstek hatası (timeout, 5xx) |
| 2 | Yeniden dene butonu | Hata ekranında "Tekrar dene" |
| 3 | (Opsiyonel) Offline mesajı | NetInfo ile bağlantı yoksa bilgi mesajı |

---

## Konu 3: Dashboard (Next.js)

### 3.1 i18n

| # | Adım | Açıklama |
|---|------|----------|
| 1 | Mesaj dosyaları | `dashboard/messages/tr.json`, `en.json` |
| 2 | getText(locale, key) | `dashboard/lib/i18n.ts` veya mevcut yapı |
| 3 | Sayfalarda kullanım | `getText(locale, "nav.sessions")` — locale cookie veya URL’den |

### 3.2 Dil değiştirici

| # | Adım | Açıklama |
|---|------|----------|
| 1 | Header | TR / EN seçimi (dropdown veya toggle) |
| 2 | Cookie | Tercihi `locale` cookie’de sakla |
| 3 | Yenileme | Locale değişince sayfayı yenile veya client state güncelle |

### 3.3 Hata sayfası

| # | Adım | Açıklama |
|---|------|----------|
| 1 | `app/error.tsx` | Next.js App Router global error boundary |
| 2 | Mesaj | Kullanıcı dostu "Bir hata oluştu" + yeniden dene |

---

## Konu 4: Backend (ek)

### 4.1 Rate limit header’ları

| Adım | Durum | Açıklama |
|------|--------|----------|
| triage/turn, feedback | ✅ | `X-RateLimit-Limit`, `Remaining`, `Reset` zaten ekleniyor |
| send-summary | — | İsteğe bağlı: aynı header’lar veya ayrı limit (örn. 5/dk) |

### 4.2 send-summary rate limit

- IP veya cihaz bazlı limit (örn. 5 istek/dakika).
- Rate limit middleware’e `/v1/triage/send-summary` path’i eklenebilir.

### 4.3 E-posta alternatifi

- Resend yerine SMTP veya başka sağlayıcı için `email_sender_*` modülü (örn. `email_sender_smtp.py`) ve env ile seçim.

---

## Konu 5: Test ve kalite

### 5.1 Backend testleri

| # | Adım | Açıklama |
|---|------|----------|
| 1 | send-summary E2E | Mock Supabase + mock e-posta; POST ve 200/404 |
| 2 | export-summary | POST payload → 200 ve text/plain içeriği |
| 3 | Unit | `email_summary.build_summary_body`, `i18n.get_text` |

### 5.2 Mobil E2E

- Detox veya Maestro: giriş → semptom girişi → triaj → sonuç ekranı.

### 5.3 Dashboard E2E

- Playwright: login → sessions listesi → detay.

---

## Konu 6: Dokümantasyon ve operasyon

| # | Adım | Açıklama |
|---|------|----------|
| 1 | Deploy runbook | Backend/dashboard/mobil deploy adımları, env listesi, rollback |
| 2 | Mimari diyagram | Backend ↔ Supabase ↔ Mobile/Dashboard (Mermaid) |
| 3 | CHANGELOG | Yeni özellikleri `CHANGELOG.md` [Unreleased] altına ekleme |

---

## Konu 7: Güvenlik ve uyum

| # | Adım | Açıklama |
|---|------|----------|
| 1 | KVKK / GDPR | Gizlilik metni, saklama süreleri, silme talebi |
| 2 | Push token | Şifreli veya kısıtlı saklama; çıkışta silme |

---

## Önerilen sıra

1. **Konu 1** — ✅ Tamamlandı (fallback eklendi).
2. **Konu 2 (Mobil)** — i18n → dil seçimi → özet e-posta / metin indirme → push → error boundary → retry.
3. **Konu 3 (Dashboard)** — i18n → dil değiştirici → error sayfası.
4. **Konu 4** — send-summary rate limit, isteğe bağlı e-posta alternatifi.
5. **Konu 5–7** — Test, dokümantasyon, güvenlik.

Sonraki adım: **Konu 2.1 (Mobil i18n)** ile devam edebilirsiniz; isterseniz bir sonraki mesajda 2.1 için dosya bazlı patch’ler yazabilirim.
