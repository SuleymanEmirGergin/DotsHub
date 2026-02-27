# Sonraki adımlar – Ne yapılabilir?

Bu belge, projede sırayla veya ihtiyaca göre yapılabilecek geliştirmeleri listeler.

---

## 1. Entegrasyonlar (manuel)

Bazı dosyalar EPERM nedeniyle otomatik düzenlenemedi; aşağıdakileri **elle** eklemeniz gerekebilir.

- **Backend `main.py`**
  - `app.include_router(summary_email.router, prefix="/v1")` – oturum özeti e-posta endpoint’i
  - `SecurityHeadersMiddleware` – `docs/SECURITY_HEADERS_INTEGRATION.md` içindeki adımlar
  - Lifespan’ta `app.state.app_env = settings.APP_ENV`
- **Backend**: `summary_email` route’unda `get_supabase` veya tablo adı farklıysa import/tablo adını güncelleyin.

---

## 2. Mobil

| Madde | Açıklama |
|-------|----------|
| **i18n kullanımı** | `_layout.tsx`’te `<I18nProvider>` ile sarmalayıp ekranlarda `useI18n()` ve `t("result.openOnMap")` kullanın. |
| **Dil seçimi** | Ayarlar veya ilk açılışta TR/EN seçimi; `expo-localization` ile cihaz diline göre varsayılan. |
| **Özet e-posta UI** | Sonuç ekranında “Özeti e-postaya gönder” alanı + `POST /v1/triage/send-summary` çağrısı. |
| **Push izni** | Ayarlar veya ilk oturum sonrası `requestPushPermission()` / `getExpoPushTokenAsync()`; token’ı backend’e kaydedin. |
| **Error boundary** | React Error Boundary ile ekran hatalarını yakalayıp kullanıcıya mesaj gösterin. |
| **Offline / retry** | Ağ hatası durumunda yeniden deneme ve (isteğe bağlı) basit offline davranış. |

---

## 3. Dashboard

| Madde | Açıklama |
|-------|----------|
| **i18n kullanımı** | Sayfalarda `getText(locale, "nav.sessions")`; locale’i cookie veya URL’den alın. |
| **Dil değiştirici** | Header’da TR/EN seçimi; tercihi cookie’de saklayıp sayfaları yenileyin. |
| **Hata sayfası** | `app/error.tsx` ile global hata yakalama ve kullanıcı dostu mesaj. |

---

## 4. Backend

| Madde | Açıklama |
|-------|----------|
| **Rate limit header’ları** | Yanıtta `X-RateLimit-Limit`, `X-RateLimit-Remaining` ekleyin. |
| **send-summary rate limit** | `/v1/triage/send-summary` için IP veya cihaz bazlı limit. |
| **E-posta alternatifi** | Resend yerine SMTP veya başka sağlayıcı için `email_sender_*` modülü. |

---

## 5. Test ve kalite

| Madde | Açıklama |
|-------|----------|
| **send-summary E2E** | Backend test: mock session + mock e-posta ile POST ve yanıt kontrolü. |
| **Mobil E2E** | Detox veya Maestro ile kritik akış (giriş → triaj → sonuç). |
| **Eksik unit testler** | `email_summary.build_summary_body`, `i18n.getText` vb. için testler. |

---

## 6. Dokümantasyon ve operasyon

| Madde | Açıklama |
|-------|----------|
| **Deploy runbook** | Backend/dashboard/mobil deploy adımları, env listesi, rollback. |
| **Mimari diyagram** | Backend ↔ Supabase ↔ Mobile/Dashboard akışı (Mermaid veya görsel). |
| **CHANGELOG** | Yeni özellikleri `CHANGELOG.md` içinde [Unreleased] altına ekleyin. |

---

## 7. Güvenlik ve uyum

| Madde | Açıklama |
|-------|----------|
| **KVKK / GDPR** | Gizlilik metni, veri saklama süreleri, silme talebi akışı. |
| **Push token saklama** | Token’ları şifreli veya erişim kısıtlı saklayın; çıkışta silme. |

---

Öncelik için: önce **entegrasyonlar (1)** ve **mobil/dashboard i18n + özet e-posta UI (2–3)** ile başlamak mantıklı; ardından test, dokümantasyon ve güvenlik maddelerine geçebilirsiniz.
