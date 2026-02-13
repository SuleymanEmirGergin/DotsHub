/**
 * Dashboard i18n: server/client-safe getText with locale from cookie or default.
 * For Next.js: use getLocaleFromHeaders or pass locale explicitly in server components;
 * in client components use useLocale (from a small context or searchParams).
 */

export type Locale = "tr" | "en";

import tr from "../messages/tr.json";
import en from "../messages/en.json";

const messages: Record<Locale, Record<string, unknown>> = {
  tr: tr as Record<string, unknown>,
  en: en as Record<string, unknown>,
};

const defaultLocale: Locale = "tr";

/**
 * Get message by dot path for a given locale.
 * e.g. getText("tr", "nav.sessions") -> "Oturumlar"
 */
export function getText(locale: Locale, key: string): string {
  const parts = key.split(".");
  let value: unknown = messages[locale] ?? messages[defaultLocale];
  for (const part of parts) {
    if (value == null || typeof value !== "object") return key;
    value = (value as Record<string, unknown>)[part];
  }
  return typeof value === "string" ? value : key;
}

/**
 * Get text using default locale (e.g. when no request context).
 */
export function getTextDefault(key: string, locale: Locale = defaultLocale): string {
  return getText(locale, key);
}

/**
 * Parse locale from Accept-Language or similar (e.g. "tr-TR,en;q=0.9" -> "tr").
 */
export function parseLocaleFromHeader(header: string | null): Locale {
  if (!header) return defaultLocale;
  const first = header.split(",")[0]?.trim().toLowerCase();
  if (first?.startsWith("tr")) return "tr";
  if (first?.startsWith("en")) return "en";
  return defaultLocale;
}

export { defaultLocale, messages };
