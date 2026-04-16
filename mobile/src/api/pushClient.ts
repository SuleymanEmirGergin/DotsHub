/**
 * Push token kaydı — Expo Push Token'ı backend'e gönderir.
 * POST /v1/triage/push-token (body: expo_push_token, device_id, platform, locale)
 */

import { Platform } from "react-native";
import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";

/** Backend locale format: tr-TR, en-US, de-DE, ru-RU, ar (max 10 char). */
function toBackendLocale(locale: string): string {
  const map: Record<string, string> = { tr: "tr-TR", en: "en-US", de: "de-DE", ru: "ru-RU", ar: "ar" };
  return map[locale] ?? "tr-TR";
}

function resolveErrorMessage(err: unknown, status: number, fallback: string): string {
  if (typeof err === "object" && err !== null) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return `${fallback} (HTTP ${status})`;
}

export async function registerPushToken(
  expoPushToken: string,
  deviceId: string,
  locale: string = "tr",
): Promise<{ ok: boolean }> {
  const res = await fetchWithTimeout(
    `${API_BASE}/v1/triage/push-token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expo_push_token: expoPushToken,
        device_id: deviceId,
        platform: Platform.OS,
        locale: toBackendLocale(locale),
      }),
    },
    10000,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(resolveErrorMessage(err, res.status, "Register failed"));
  }
  return (await res.json()) as { ok: boolean };
}

/**
 * Push token unregister — device için push kaydını pasifleştirir.
 * DELETE /v1/triage/push-token (body: device_id)
 */
export async function unregisterPushToken(
  deviceId: string,
): Promise<{ ok: boolean }> {
  const res = await fetchWithTimeout(
    `${API_BASE}/v1/triage/push-token`,
    {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId }),
    },
    10000,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(resolveErrorMessage(err, res.status, "Unregister failed"));
  }
  return (await res.json()) as { ok: boolean };
}
