/**
 * Mobile i18n: locale messages and getText helper.
 * Use with expo-localization for system locale, or set locale manually.
 */

export type Locale = "tr" | "en" | "de" | "ru" | "ar";

import tr from "./tr.json";
import en from "./en.json";
import de from "./de.json";
import ru from "./ru.json";
import ar from "./ar.json";

const messages: Record<Locale, Record<string, unknown>> = {
  tr: tr as Record<string, unknown>,
  en: en as Record<string, unknown>,
  de: de as Record<string, unknown>,
  ru: ru as Record<string, unknown>,
  ar: ar as Record<string, unknown>,
};

/** Dil seçicide gösterilecek tüm diller (kod, etiket). */
export const SUPPORTED_LOCALES: Locale[] = ["tr", "en", "de", "ru", "ar"];

let currentLocale: Locale = "tr";

export function setLocale(locale: Locale): void {
  currentLocale = locale;
}

export function getLocale(): Locale {
  return currentLocale;
}

/**
 * Get nested message by dot path, e.g. getText("result.openOnMap") -> "Haritada aç"
 * Optional first argument: locale; if omitted, uses currentLocale.
 */
export function getText(keyOrLocale: string, key?: string): string {
  const locale: Locale = key ? (keyOrLocale as Locale) : currentLocale;
  const path = key ?? keyOrLocale;
  const parts = path.split(".");
  let value: unknown = messages[locale];
  for (const part of parts) {
    if (value == null || typeof value !== "object") return path;
    value = (value as Record<string, unknown>)[part];
  }
  return typeof value === "string" ? value : path;
}

/**
 * Hook-friendly: returns { t: getText, locale, setLocale }.
 * Use in components: const { t } = useI18n();
 */
export function useI18n(): {
  t: (key: string) => string;
  locale: Locale;
  setLocale: (locale: Locale) => void;
} {
  return {
    t: getText,
    locale: currentLocale,
    setLocale,
  };
}

export default { getText, setLocale, getLocale, useI18n, messages };
