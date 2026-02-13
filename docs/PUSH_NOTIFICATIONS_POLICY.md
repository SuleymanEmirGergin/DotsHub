# Push bildirimleri politika

Bu belge, Pre-Triage (Dotshub) mobil uygulamasında push bildirimlerinin kullanımı, veri ve saklama kurallarını tanımlar.

## Amaç

- Kullanıcıya oturum sonucu veya hatırlatma gibi **işlemsel** bildirimler göndermek.
- Reklam veya pazarlama amaçlı toplu push **gönderilmez**.

## Ne zaman bildirim gönderilir

- Oturum tamamlandığında (özet hazır) – kullanıcı bu seçeneği açtıysa.
- Hatırlatma (örn. “Triajı tamamlamayı unutmayın”) – sadece kullanıcı tercihine göre.
- Zorunlu güvenlik / hesap bildirimleri (ör. şifre sıfırlama) – gerektiğinde.

## Veri ve gizlilik

- Bildirim içeriği **kişisel sağlık verisi içermemeli**; sadece “Sonucunuz hazır” gibi genel ifadeler kullanılır.
- Cihaza ait **push token** sadece bildirim gönderimi için kullanılır; üçüncü taraflarla paylaşılmaz.
- Token’lar sunucuda güvenli şekilde saklanır ve kullanıcı bildirimleri kapattığında ilgili kayıt silinebilir/güncellenir.

## Saklama

- Push token’lar, kullanıcı hesabı veya cihaz ilişkisi silindiğinde/çıkış yapıldığında kaldırılır veya devre dışı bırakılır.
- Bildirim geçmişi (içerik) uzun süreli log olarak tutulmaz; sadece teslimat durumu (başarılı/başarısız) operasyonel loglarda kısa süre saklanabilir.

## İzin

- Bildirimler **kullanıcı izni** ile açılır.
- Uygulama ilk açılışta veya ilgili özelliğe ilk girildiğinde izin istenir; reddedilirse tekrar sadece ayarlar üzerinden açılabilir.
- Ayarlarda “Bildirimleri kapat” seçeneği sunulur.

## Teknik

- Mobil tarafta **Expo Notifications** (veya FCM/APNs) kullanılır.
- Backend’de token kaydı ve gönderim için ayrı bir servis/endpoint kullanılabilir; gönderim sıklığı rate limit ile sınırlanır.

Bu politika, uygulama mağaza gereksinimleri ve KVKK/GDPR uyumuna göre güncellenebilir.
