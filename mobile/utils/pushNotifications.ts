/**
 * Push notification helpers.
 * Works with expo-notifications when available; otherwise degrades safely.
 */

import { Platform } from "react-native";

export type PushPermissionStatus = "granted" | "denied" | "undetermined";

type ExpoNotificationsLike = {
  AndroidImportance?: { DEFAULT?: number };
  getPermissionsAsync?: () => Promise<{ status?: string }>;
  requestPermissionsAsync?: () => Promise<{ status?: string }>;
  setNotificationChannelAsync?: (
    channelId: string,
    channel: {
      name: string;
      importance?: number;
      vibrationPattern?: number[];
      lightColor?: string;
    },
  ) => Promise<unknown>;
  getExpoPushTokenAsync?: (args?: { projectId?: string }) => Promise<{ data?: string }>;
  getDevicePushTokenAsync?: () => Promise<{ data?: string }>;
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

function getProjectId(): string | undefined {
  try {
    const safeRequire = Function("return require")() as (name: string) => unknown;
    const constants = safeRequire("expo-constants") as {
      expoConfig?: { extra?: { eas?: { projectId?: string } } };
      eas?: { projectId?: string };
    };
    return (
      constants?.expoConfig?.extra?.eas?.projectId ??
      constants?.eas?.projectId ??
      undefined
    );
  } catch {
    return undefined;
  }
}

export async function getPushPermissionStatus(): Promise<PushPermissionStatus> {
  const notifications = loadExpoNotifications();
  if (!notifications?.getPermissionsAsync) return "undetermined";

  const { status } = await notifications.getPermissionsAsync();
  if (status === "granted") return "granted";
  if (status === "denied") return "denied";
  return "undetermined";
}

export async function requestPushPermission(): Promise<boolean> {
  const notifications = loadExpoNotifications();
  if (!notifications?.requestPermissionsAsync) return false;

  const existing = await getPushPermissionStatus();
  if (existing === "granted") return true;
  if (existing === "denied") return false;
  const { status } = await notifications.requestPermissionsAsync();
  return status === "granted";
}

export async function setupNotificationChannel(): Promise<void> {
  const notifications = loadExpoNotifications();
  if (
    Platform.OS !== "android" ||
    !notifications?.setNotificationChannelAsync
  ) {
    return;
  }

  await notifications.setNotificationChannelAsync("default", {
    name: "Default",
    importance: notifications.AndroidImportance?.DEFAULT ?? 3,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: "#FF6B00",
  });
}

export async function getExpoPushTokenAsync(): Promise<string | null> {
  const notifications = loadExpoNotifications();
  if (!notifications?.getExpoPushTokenAsync) return null;

  const granted = await requestPushPermission();
  if (!granted) return null;
  await setupNotificationChannel();

  const tokenData = await notifications.getExpoPushTokenAsync({
    projectId: getProjectId(),
  });
  return tokenData?.data ?? null;
}

export async function getDevicePushTokenAsync(): Promise<string | null> {
  const notifications = loadExpoNotifications();
  if (!notifications?.getDevicePushTokenAsync) return null;

  const granted = await requestPushPermission();
  if (!granted) return null;
  await setupNotificationChannel();

  const tokenData = await notifications.getDevicePushTokenAsync();
  return tokenData?.data ?? null;
}
