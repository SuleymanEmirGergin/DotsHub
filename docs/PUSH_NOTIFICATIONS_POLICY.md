# Push bildirimleri politika metni

Bu belge, Dotshub mobil uygulamasında push bildirimlerinin ne zaman ve nasıl kullanılacağını tanımlar.

---

## Amaç

- Triaj sonucu hazır olduğunda kullanıcıya bildirim gönderilebilir (isteğe bağlı).
- Hatırlatma veya anket bildirimleri ileride tanımlanabilir.

## Veri

- **Expo Push Token:** Cihaza özel, bildirim göndermek için kullanılır. Backend’e `POST /v1/triage/push-token` ile kaydedilir.
- **Saklama:** Token şu an loglanır; kalıcı depolama (örn. Supabase `push_tokens` tablosu) isteğe bağlı eklenebilir.
- **Silme:** Kullanıcı "Yeni değerlendirme başlat" / "Yeni oturum" seçtiğinde mobil `unregisterPushTokenIfNeeded()` ile `DELETE /v1/triage/push-token` çağrılır (best-effort). Bildirimleri kapatma ayarı ileride eklenebilir.

## Backend–mobil push-token kontratı

Backend: `backend/app/api/routes/push_token.py`. Mobil: `mobile/src/api/pushClient.ts`, `mobile/src/hooks/usePushRegistration.ts`. Kontrat uyumlu (A.1 doğrulandı).

- **POST /v1/triage/push-token**  
  Body: `expo_push_token` (string, 10–256), `device_id` (string, 1–128), `platform` (string, max 20; mobil `Platform.OS` → `ios`/`android`), `locale` (string, max 10; mobil `toBackendLocale(locale)` → `tr-TR`, `en-US`, vb.).  
  Cevap: `{"ok": true}`. Hata: 422 (eksik/geçersiz alan), 503 (persist hatası, production'da).

- **DELETE /v1/triage/push-token**  
  Body: `device_id` (string, zorunlu). Cevap: `{"ok": true}`.

- **Mobil kullanım:** `registerPushToken(expoPushToken, deviceId, locale)` ve `unregisterPushToken(deviceId)`. `device_id`: `getDeviceId()`. Çıkış/yeni oturum: ResultScreen, ErrorScreen, EmergencyScreen’de "Yeni değerlendirme" / "Yeni oturum" butonuna basıldığında `unregisterPushTokenIfNeeded()` çağrılır (best-effort), ardından oturum sıfırlanır. İzin veya token yoksa register çağrılmaz; izin reddedilirse veya token alınamazsa `unregisterPushToken(deviceId)` çağrılır (best-effort).

## İzin

- Bildirimler yalnızca kullanıcı izin verdikten sonra gönderilir.
- İzin, ayarlar veya ilk sonuç ekranı sonrası istenebilir (`expo-notifications.requestPermissionsAsync()`).

## Ne zaman bildirim gönderilir

- **Şu an:** Sadece token kaydı yapılır; otomatik bildirim gönderimi yok.
- **İleride:** Triaj sonucu hazır olduğunda (session RESULT döndüğünde) isteğe bağlı “Sonucunuz hazır” bildirimi; oran ve sıklık ayrıca tanımlanacak.

## Gizlilik ve uyum

- KVKK/GDPR kapsamında token kişisel veri sayılabilir; saklama süresi ve silme talebi prosedürlere uygun yönetilmelidir.
- Bu politika, ileride gizlilik metni ve kullanıcı ayarları ile güncellenebilir.
