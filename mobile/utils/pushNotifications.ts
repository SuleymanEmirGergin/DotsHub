/**
 * Push bildirim izni ve token yardımcıları.
 * Kullanım: docs/PUSH_NOTIFICATIONS_MOBILE.md
 */

import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { Platform } from "react-native";

export type PushPermissionStatus = "granted" | "denied" | "undetermined";

/**
 * Mevcut push iznini döndürür.
 */
export async function getPushPermissionStatus(): Promise<PushPermissionStatus> {
  const { status } = await Notifications.getPermissionsAsync();
  if (status === "granted") return "granted";
  if (status === "denied") return "denied";
  return "undetermined";
}

/**
 * Kullanıcıdan push bildirimi izni ister. granted ise true döner.
 */
export async function requestPushPermission(): Promise<boolean> {
  const existing = await getPushPermissionStatus();
  if (existing === "granted") return true;
  if (existing === "denied") return false;
  const { status } = await Notifications.requestPermissionsAsync();
  return status === "granted";
}

/**
 * Android için varsayılan bildirim kanalını oluşturur (Android 8+).
 */
export async function setupNotificationChannel(): Promise<void> {
  if (Platform.OS !== "android") return;
  await Notifications.setNotificationChannelAsync("default", {
    name: "Varsayılan",
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: "#FF6B00",
  });
}

/**
 * Expo Push Token döndürür (Expo servisi kullanılıyorsa).
 * İzin yoksa null.
 */
export async function getExpoPushTokenAsync(): Promise<string | null> {
  const granted = await requestPushPermission();
  if (!granted) return null;
  await setupNotificationChannel();
  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ?? (Constants as { eas?: { projectId?: string } }).eas?.projectId;
  const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: projectId ?? undefined,
  });
  return tokenData.data;
}

/**
 * Cihaz push token'ı (FCM/APNs) – kendi backend ile gönderim için.
 */
export async function getDevicePushTokenAsync(): Promise<string | null> {
  const granted = await requestPushPermission();
  if (!granted) return null;
  await setupNotificationChannel();
  const tokenData = await Notifications.getDevicePushTokenAsync();
  return tokenData.data;
}
