# Gizlilik ve güvenlik notu

Bu belge, Dotshub projesinde veri ve güvenlikle ilgili genel prensipleri özetler. Ürün seviyesi gizlilik politikası ve KVKK/GDPR metinleri ayrıca hazırlanmalıdır.

---

## Toplanan / işlenen veriler

- **Triaj oturumu:** Kullanıcı girdisi (semptomlar, cevaplar), oturum ID, sonuç (önerilen branş, güven skoru vb.). Supabase’de saklanabilir.
- **Geri bildirim:** Oylama (up/down), isteğe bağlı yorum. Oturumla ilişkili kaydedilir.
- **Özet e-posta:** Gönderilen e-posta adresi ve oturum özeti; e-posta sağlayıcı (örn. Resend) üzerinden iletilir.
- **Push token:** Expo Push Token, cihaza özeldir; backend’e `POST /v1/triage/push-token` ile gönderilir. Şu an loglanır; kalıcı depolama isteğe bağlı.

---

## Saklama ve silme

- Oturum ve feedback verileri: Supabase’de; saklama süresi ve silme politikası operasyonel gereklere göre tanımlanmalı.
- Push token: İleride kullanıcı çıkışı veya bildirim kapatma ile silinebilir (akış dokümante edilmeli).
- E-posta adresi: Sadece özet gönderimi için kullanılır; ayrı bir “e-posta listesi” tutulmuyor.

---

## Güvenlik önlemleri

- **Dashboard admin API:** Tüm `/api/admin/*` proxy route’ları `requireAdmin()` ile korunur (Supabase Auth + admin_users); yetkisiz erişim engellenir.
- **API:** CORS kısıtlı; rate limit (triage, feedback, send-summary) uygulanıyor.
- **Header’lar:** Production’da SecurityHeadersMiddleware (HSTS, X-Content-Type-Options vb.) kullanılabilir.
- **Gizlilik:** PII maskeleme (log’larda); hassas env değişkenleri (API key, Supabase key) ortam üzerinden verilir, repoda tutulmaz.

---

## Uygulama içi gizlilik linki

- **Dashboard:** `/privacy` sayfası mevcut; metin `messages` (tr/en) ile i18n. Bu sayfa, bu belgedeki özeti kullanıcıya yansıtan **uygulama içi kısa özet**tir (toplanan veriler, saklama, güvenlik, haklar, KVKK/GDPR referansı).
- **Mobil:** Giriş ekranında "Gizlilik politikası" linki, `EXPO_PUBLIC_PRIVACY_URL` tanımlıysa gösterilir ve tarayıcıda açar; genelde dashboard `/privacy` veya statik politika URL’i kullanılır.

---

## KVKK / GDPR

- Kullanıcıya açık bir **gizlilik metni** ve **aydınlatma metni** yayımlanmalıdır.
- Veri saklama süreleri, silme talebi ve veri taşınabilirliği prosedürleri tanımlanmalıdır.
- Bu doküman hukuki metin yerine geçmez; nihai politika hukuk ve ürün ekibi ile netleştirilmelidir.
