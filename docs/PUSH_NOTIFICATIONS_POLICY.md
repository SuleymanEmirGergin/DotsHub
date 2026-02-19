# Push bildirimleri politika metni

Bu belge, Dotshub mobil uygulamasında push bildirimlerinin ne zaman ve nasıl kullanılacağını tanımlar.

---

## Amaç

- Triaj sonucu hazır olduğunda kullanıcıya bildirim gönderilebilir (isteğe bağlı).
- Hatırlatma veya anket bildirimleri ileride tanımlanabilir.

## Veri

- **Expo Push Token:** Cihaza özel, bildirim göndermek için kullanılır. Backend’e `POST /v1/triage/push-token` ile kaydedilir.
- **Saklama:** Token şu an loglanır; kalıcı depolama (örn. Supabase `push_tokens` tablosu) isteğe bağlı eklenebilir.
- **Silme:** Kullanıcı bildirimleri kapatırsa veya uygulamadan çıkış yaparsa token silinebilir (ileride uygulanacak akış).

## Backend–mobil push-token kontratı

- **POST /v1/triage/push-token**  
  Body (zorunlu): `expo_push_token` (string, 10–256 karakter), `device_id` (string, 1–128 karakter).  
  Opsiyonel: `platform` (örn. `ios` / `android`), `locale` (örn. `tr-TR`, `en-US`).  
  Cevap: `{"ok": true}`. Hata: 422 (eksik/geçersiz alan), 503 (persist hatası, production'da).

- **DELETE /v1/triage/push-token**  
  Body: `device_id` (string, zorunlu). Cevap: `{"ok": true}`.

- **Mobil kullanım:** `registerPushToken(expoPushToken, deviceId, locale)` ve `unregisterPushToken(deviceId)`. `device_id` kaynağı: `getDeviceId()` (Expo Constants.sessionId / installationId veya fallback). Token alınıp device_id üretilemezse register çağrılmamalı; getDeviceId() şu an her zaman string döndürür (fallback ile).

## İzin

- Bildirimler yalnızca kullanıcı izin verdikten sonra gönderilir.
- İzin, ayarlar veya ilk sonuç ekranı sonrası istenebilir (`expo-notifications.requestPermissionsAsync()`).

## Ne zaman bildirim gönderilir

- **Şu an:** Sadece token kaydı yapılır; otomatik bildirim gönderimi yok.
- **İleride:** Triaj sonucu hazır olduğunda (session RESULT döndüğünde) isteğe bağlı “Sonucunuz hazır” bildirimi; oran ve sıklık ayrıca tanımlanacak.

## Gizlilik ve uyum

- KVKK/GDPR kapsamında token kişisel veri sayılabilir; saklama süresi ve silme talebi prosedürlere uygun yönetilmelidir.
- Bu politika, ileride gizlilik metni ve kullanıcı ayarları ile güncellenebilir.
