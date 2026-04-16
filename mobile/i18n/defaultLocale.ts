/**
 * İlk açılışta kullanılacak locale: önce AsyncStorage, yoksa cihaz dili (expo-localization).
 */
import type { Locale } from "./index";
import { SUPPORTED_LOCALES } from "./index";
import { getStoredLocale } from "./storage";

const DEFAULT_LOCALE: Locale = "tr";

/**
 * Cihaz dil kodunu desteklenen locale'e eşler (tr, en, de, ru, ar).
 * Örn: "tr-TR" -> "tr", "en-US" -> "en", "de" -> "de".
 */
function mapDeviceLocaleToAppLocale(languageCode: string): Locale | null {
  const code = (languageCode || "").trim().toLowerCase().split("-")[0];
  if (!code) return null;
  if (SUPPORTED_LOCALES.includes(code as Locale)) return code as Locale;
  return null;
}

function tryGetDeviceLocale(): string {
  // Avoid hard dependency on expo-localization in environments where it is not installed.
  try {
    const safeRequire = Function("return require")() as (name: string) => unknown;
    const mod = safeRequire("expo-localization") as {
      getLocales?: () => Array<{ languageCode?: string; languageTag?: string }>;
    };
    const locales = typeof mod?.getLocales === "function" ? mod.getLocales() : [];
    const first = locales?.[0];
    return first?.languageCode ?? first?.languageTag ?? "";
  } catch {
    // ignore
  }

  try {
    return Intl.DateTimeFormat().resolvedOptions().locale ?? "";
  } catch {
    return "";
  }
}

/**
 * Uygulama açılışında kullanılacak locale:
 * 1) AsyncStorage'da kayıtlı varsa onu döndür.
 * 2) Cihaz dilinden eşleşen varsa onu döndür.
 * 3) Yoksa "tr".
 */
export async function getDefaultLocale(): Promise<Locale> {
  const stored = await getStoredLocale();
  if (stored) return stored;

  const mapped = mapDeviceLocaleToAppLocale(tryGetDeviceLocale());
  if (mapped) return mapped;

  return DEFAULT_LOCALE;
}
