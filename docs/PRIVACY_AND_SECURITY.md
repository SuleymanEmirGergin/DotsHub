# Gizlilik ve güvenlik notu

> **Kullanıcıya yönelik aydınlatma metni** ayrı bir dokümandadır:
> [`PRIVACY_NOTICE.md`](PRIVACY_NOTICE.md). Bu dosya kullanıcı görmez —
> mühendislik tarafının hızlı referansıdır.

Bu belge, Triaige projesinde veri ve güvenlikle ilgili genel prensipleri ve teknik kontrolleri özetler. KVKK/GDPR uyumlu **kullanıcı yüzlü** metin için yukarıdaki bağlantıya gidin; kanonik kaynak `dashboard/messages/{tr,en}.json:privacy.*` anahtarları + dashboard `/privacy` sayfasıdır. Saklama süreleri için: [`RETENTION_POLICY.md`](RETENTION_POLICY.md).

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

- **API:** CORS kısıtlı; rate limit (triage, feedback, send-summary) uygulanıyor.
- **Header’lar:** Production’da SecurityHeadersMiddleware (HSTS, X-Content-Type-Options vb.) kullanılabilir.
- **Gizlilik:** PII maskeleme (log’larda); hassas env değişkenleri (API key, Supabase key) ortam üzerinden verilir, repoda tutulmaz.

---

## Uygulama içi gizlilik linki

- **Dashboard:** `/privacy` sayfası mevcut; metin `messages` (tr/en) ile i18n.
- **Mobil:** Giriş ekranında "Gizlilik politikası" linki, `EXPO_PUBLIC_PRIVACY_URL` tanımlıysa gösterilir ve tarayıcıda açar; genelde dashboard `/privacy` veya statik politika URL’i kullanılır.

---

## KVKK / GDPR

- **Aydınlatma metni** (KVKK Md.10 + GDPR Art.13) yayında: bkz. [`PRIVACY_NOTICE.md`](PRIVACY_NOTICE.md) — DRAFT v0.2; hukuk onayı bekliyor.
- **Saklama süreleri** kod sabiti olarak: [`RETENTION_POLICY.md`](RETENTION_POLICY.md). Cron job şablonu: `backend/sql/20260427_retention_purge.sql`.
- **Silme talebi**: `DELETE /v1/me/sessions/{id}` endpoint'i mevcut ([backend/app/api/routes/data_rights.py](../backend/app/api/routes/data_rights.py)). Tombstone + 90 gün grace + fiziksel delete.
- **Açık rıza akışı** henüz mobil intro'da ayrıştırılmadı — Slice 3'te yapılacak (`COMPLIANCE_CHECK_2026_04.md:KR-1`).
- **Sub-processor envanteri** (DPA + SCC durumu) henüz yok — `docs/SUB_PROCESSORS.md` Slice 4'te.
- Bu doküman hukuki metin yerine geçmez; nihai politika hukuk ve ürün ekibi ile netleştirilmelidir.
