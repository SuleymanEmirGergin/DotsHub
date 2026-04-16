# Yeni özellik ve tech debt – Sıra sıra plan

Bu belge, seçilen maddelerin uygulama sırasını ve kısa adımlarını listeler.

---

## Tamamlanan

### 1. Mobil: Offline / retry ✅

- **Yapılanlar:**
  - Ağ hatası ve zaman aşımı için i18n: `error.connectionError`, `error.timeout` (tr, en, de, ru, ar).
  - `triageClient`: AbortError için `TIMEOUT`, diğer ağ hataları için `NETWORK_ERROR` kodu dönüyor.
  - `ErrorScreen`: NETWORK_ERROR ve TIMEOUT için locale’e göre mesaj gösterimi (Yeniden dene zaten vardı).
  - `HistoryScreen`: Geçmiş listesi isteği `fetchWithTimeout` (10 sn) ile yapılıyor; hata durumunda “Tekrar dene” butonu mevcut.
- **İsteğe bağlı (ileride):** `@react-native-community/netinfo` ile “İnternet yok” banner’ı ve tekrar bağlanınca otomatik yeniden deneme.

---

## Sıradaki maddeler (sıra ile)

### 2. Mobil: Metni indir / paylaş ✅ (netleştirildi)

- **Hedef:** `export-summary` yanıtını kullanıcıya paylaştırmak veya “dosyaya kaydet” ile indirtmek.
- **Mevcut durum:** “Metni indir” butonu `exportSummary()` çağırıyor, gelen plain text `Share.share({ message, title })` ile sistem paylaşım menüsüne açılıyor; kullanıcı “Dosyaya kaydet”, WhatsApp, e-posta vb. seçebiliyor.
- **Yapılan:** Share başlığı `t("summary.title")` yerine `t("result.shareTitle")` yapıldı (summary.title i18n’de yoktu).
- **İsteğe bağlı (ileride):** `expo-file-system` ile metni geçici `.txt` dosyasına yazıp `expo-sharing.shareAsync(uri)` ile doğrudan “Dosyaya kaydet” ve dosya adı (örn. `triyaj-ozeti.txt`) vermek.
- **Tahmini:** Tamamlandı (opsiyonel dosya adı için küçük).

---

### 3. Push token: çıkışta silme ✅

- **Hedef:** Kullanıcı çıkış yaptığında veya “Bildirimleri kapat” seçildiğinde `DELETE /v1/triage/push-token` çağrılması; dokümanda bu akışın net yazılması.
- **Adımlar:**
  1. Mobil: Çıkış veya “bildirimleri kapat” akışında `getDeviceId()` + `unregisterPushToken(deviceId)` çağrısı ekle (uygulama içi çıkış nerede yönetiliyorsa orada).
  2. Eğer uygulamada açık “çıkış” ekranı yoksa: ayarlar veya profil içinde “Bildirimleri kapat” seçeneği ile sadece `unregisterPushToken` çağrılabilir.
  3. `docs/PUSH_NOTIFICATIONS_POLICY.md`: “Silme: Kullanıcı çıkış yaptığında veya bildirimleri kapattığında mobil uygulama DELETE /v1/triage/push-token çağırır.” cümlesini ekle/güncelle.
- **Yapılanlar:** `pushClient.ts`: `unregisterPushTokenIfNeeded()`; ResultScreen, ErrorScreen, EmergencyScreen'de butonda önce unregister (best-effort), sonra `resetSession()`; `PUSH_NOTIFICATIONS_POLICY.md` güncellendi.
- **İleride (isteğe bağlı):** Ayarlarda "Bildirimleri kapat" ile sadece unregister.

---

### 4. Backend: send-summary unit/E2E ✅

- **Hedef:** Mock session + mock e-posta ile `POST /v1/triage/send-summary` testi (200, 404, 429).
- **Adımlar:**
  1. `backend/tests/test_summary_export_route.py` veya yeni `test_send_summary_route.py`: Supabase/session mock’u ile send-summary endpoint’ini test et.
  2. Senaryolar: session yok → 404; geçerli session + e-posta → 200 (e-posta gönderimi mock); rate limit aşımı → 429.
  3. İsteğe bağlı: export-summary ile aynı dosyada veya ayrı modülde tutulabilir.
- **Yapılanlar:** Testler `test_summary_export_route.py` içinde mevcut (404, 200 mock, 422, 429); doğrulandı.

---

### 5. Dashboard: yükleme durumu ✅ (skeleton / “Yükleniyor…”)

- **Hedef:** Admin sayfalarında (sessions, feedback, analytics) veri gelirken skeleton veya “Yükleniyor…” göstermek.
- **Adımlar:**
  1. Server component’lerde veri çekilirken loading state’i nasıl yansıtıldığını kontrol et (Next.js’te `loading.tsx` veya sayfa içi state).
  2. Sessions, feedback, analytics sayfalarında ilk yüklemede skeleton bileşeni veya ortalanmış “Yükleniyor…” metni ekle.
  3. `common.loading` zaten messages’ta var; tutarlı kullan.
- **Yapılanlar:** `dashboard/app/admin/loading.tsx` eklendi: locale cookie ile `common.loading` metni, spinner ve kısa skeleton blokları; tüm admin sayfaları (sessions, feedback, analytics vb.) için geçerli.

---

### 6. Mimari doküman güncelleme ✅

- **Hedef:** Rate limit / Redis’in mimaride nerede kullanıldığını belgelemek.
- **Adımlar:**
  1. `docs/ARCHITECTURE.md` (veya ilgili mimari belge): “Rate limiting” / “Redis” kısa bölümü ekle; triage, send-summary, admin limitlerinin Redis ile paylaşıldığını yaz.
  2. Mevcut Mermaid diyagramına (isteğe bağlı) Redis kutusu veya not eklenebilir.
  3. `docs/RATE_LIMIT_REDIS.md` zaten detaylı; mimari doc’ta oraya referans ver.
- **Yapılanlar:** `docs/ARCHITECTURE.md` içinde "Rate limiting ve Redis" bölümü eklendi (triage, send-summary, admin tablosu; RATE_LIMIT_REDIS.md referansı); Veri bölümünde Redis maddesi güncellendi.

---

## Uygulama sırası özeti

| Sıra | Madde | Durum |
|------|--------|--------|
| 1 | Mobil: Offline / retry | ✅ Tamamlandı |
| 2 | Mobil: Metni indir / paylaş | ✅ Netleştirildi (Share başlığı düzeltildi) |
| 3 | Push token: çıkışta silme | ✅ Tamamlandı |
| 4 | Backend: send-summary testi | ✅ Tamamlandı |
| 5 | Dashboard: yükleme durumu | ✅ Tamamlandı |
| 6 | Mimari doküman güncelleme | ✅ Tamamlandı |

Her madde tamamlandıkça bu tabloda “Tamamlandı” işaretlenebilir.
