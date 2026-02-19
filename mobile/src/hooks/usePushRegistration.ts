/**
 * Push bildirim izni isteyip token alır ve backend'e kaydeder.
 * Uygulama açılışında çağrılır, bir kez çalışır.
 */

import { useEffect, useRef } from "react";
import { registerPushToken, unregisterPushToken } from "@/src/api/pushClient";
import { getDeviceId } from "@/utils/deviceId";

type ExpoNotificationsLike = {
  requestPermissionsAsync?: () => Promise<{ status?: string }>;
  getExpoPushTokenAsync?: (args?: { projectId?: string }) => Promise<{ data?: string }>;
};

function loadExpoNotifications(): ExpoNotificationsLike | null {
  try {
    const safeRequire = Function("return require")() as (name: string) => unknown;
    const mod = safeRequire("expo-notifications") as ExpoNotificationsLike;
    return mod ?? null;
  } catch {
    return null;
  }
}

/** @param locale App locale (tr/en/de/ru/ar) for backend; optional, defaults to "tr". */
export function usePushRegistration(locale: string = "tr"): void {
  const doneRef = useRef(false);

  useEffect(() => {
    if (doneRef.current) return;

    let cancelled = false;
    (async () => {
      try {
        const notifications = loadExpoNotifications();
        if (!notifications?.requestPermissionsAsync || !notifications.getExpoPushTokenAsync) return;

        const deviceId = getDeviceId()?.trim();
        if (!deviceId) return;
        const { status } = await notifications.requestPermissionsAsync();
        if (cancelled) return;
        if (status !== "granted") {
          try {
            await unregisterPushToken(deviceId);
          } catch {
            // Permission denied ve unregister hatasında UI akışını kesme
          }
          doneRef.current = true;
          return;
        }

        const tokenData = await notifications.getExpoPushTokenAsync({
          projectId: process.env.EXPO_PUBLIC_PROJECT_ID ?? undefined,
        });
        const token = tokenData?.data;
        if (cancelled) return;
        if (!token) {
          try {
            await unregisterPushToken(deviceId);
          } catch {
            // Token alınamadıysa eski kayıt temizleme denemesi best-effort
          }
          doneRef.current = true;
          return;
        }

        await registerPushToken(token, deviceId, locale);
        doneRef.current = true;
      } catch {
        // Expo Go'da veya izin reddedildiğinde sessizce atla
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locale]);
}
