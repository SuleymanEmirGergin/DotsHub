# Push bildirimleri – Mobil (Expo) entegrasyonu

Bildirim izni isteme ve token’ı backend’e gönderme adımları.

## Bağımlılık

```bash
npx expo install expo-notifications
```

## İzin isteme

Kullanıcıdan push bildirimi izni almak için (ör. ayarlar ekranında veya ilk oturum sonrası):

```ts
import * as Notifications from "expo-notifications";

async function requestPushPermission(): Promise<boolean> {
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === "granted") return true;
  const { status } = await Notifications.requestPermissionsAsync();
  return status === "granted";
}
```

## Android kanalı (Android 8+)

```ts
import * as Notifications from "expo-notifications";

Notifications.setNotificationChannelAsync("default", {
  name: "Varsayılan",
  importance: Notifications.AndroidImportance.DEFAULT,
  vibrationPattern: [0, 250, 250, 250],
  lightColor: "#FF6B00",
});
```

## Push token alıp backend’e gönderme

Expo Push Token (Expo’nun kendi servisi kullanılıyorsa):

```ts
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";

async function registerForPushAndSendToken() {
  const hasPermission = await requestPushPermission();
  if (!hasPermission) return null;

  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  if (!projectId) {
    console.warn("EAS projectId not set; push token may be invalid");
  }

  const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: projectId as string | undefined,
  });
  const token = tokenData.data;
  // Backend'e POST ile gönder: { device_id, push_token, platform: "ios"|"android" }
  return token;
}
```

FCM/APNs token’ı doğrudan almak (kendi backend’inizle gönderim):

```ts
import * as Notifications from "expo-notifications";

async function getDevicePushToken(): Promise<string | null> {
  const hasPermission = await requestPushPermission();
  if (!hasPermission) return null;
  const tokenData = await Notifications.getDevicePushTokenAsync();
  return tokenData.data;
}
```

## Bildirim dinleme (uygulama açıkken)

```ts
Notifications.addNotificationReceivedListener((notification) => {
  console.log("Received:", notification);
});

Notifications.addNotificationResponseReceivedListener((response) => {
  // Kullanıcı bildirime tıkladı
  const data = response.notification.request.content.data;
  // Örn. session_id ile sonuç sayfasına yönlendir
});
```

## Ayarlarda “Bildirimleri kapat”

- Token’ı backend’den kaldırmak için API çağrısı yapın (örn. `DELETE /v1/me/push-token`).
- Uygulama içinde “bildirimler kapalı” durumunu saklayıp yeni bildirim göndermeyin.

Politika özeti için: `docs/PUSH_NOTIFICATIONS_POLICY.md`.
