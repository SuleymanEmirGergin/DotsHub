/**
 * Push bildirim izni isteyip token alır ve backend'e kaydeder.
 * Uygulama açılışında çağrılır, bir kez çalışır.
 */

import { useEffect, useRef } from "react";
import { registerPushToken, unregisterPushToken } from "@/src/api/pushClient";
import { addPushLifecycleBreadcrumb } from "@/src/observability/breadcrumb";
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
          addPushLifecycleBreadcrumb("permission_denied", { status });
          try {
            await unregisterPushToken(deviceId);
            addPushLifecycleBreadcrumb("unregistered", { reason: "permission_denied" });
          } catch (err) {
            // Permission denied ve unregister hatasında UI akışını kesme
            addPushLifecycleBreadcrumb("unregister_failed", {
              reason: "permission_denied",
              error: err instanceof Error ? err.message : String(err),
            });
          }
          doneRef.current = true;
          return;
        }
        addPushLifecycleBreadcrumb("permission_granted");

        const tokenData = await notifications.getExpoPushTokenAsync({
          projectId: process.env.EXPO_PUBLIC_PROJECT_ID ?? undefined,
        });
        const token = tokenData?.data;
        if (cancelled) return;
        if (!token) {
          addPushLifecycleBreadcrumb("token_missing");
          try {
            await unregisterPushToken(deviceId);
            addPushLifecycleBreadcrumb("unregistered", { reason: "token_missing" });
          } catch (err) {
            // Token alınamadıysa eski kayıt temizleme denemesi best-effort
            addPushLifecycleBreadcrumb("unregister_failed", {
              reason: "token_missing",
              error: err instanceof Error ? err.message : String(err),
            });
          }
          doneRef.current = true;
          return;
        }
        addPushLifecycleBreadcrumb("token_acquired");

        try {
          await registerPushToken(token, deviceId, locale);
          addPushLifecycleBreadcrumb("registered", { locale });
        } catch (err) {
          addPushLifecycleBreadcrumb("register_failed", {
            error: err instanceof Error ? err.message : String(err),
          });
          throw err;
        }
        doneRef.current = true;
      } catch {
        // Expo Go'da veya izin reddedildiğinde sessizce atla.
        // Breadcrumbs above already captured the specific failure
        // point if any reached this catch.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locale]);
}
