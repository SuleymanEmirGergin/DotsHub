/**
 * Dil tercihini AsyncStorage ile saklama.
 * Key: @dotshub/locale — değer: tr | en | de | ru | ar
 */
import type { Locale } from "./index";
import { SUPPORTED_LOCALES } from "./index";

const LOCALE_STORAGE_KEY = "@dotshub/locale";
const memoryStore = new Map<string, string>();

type AsyncStorageLike = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
};

let asyncStorageRef: AsyncStorageLike | null | undefined;

function getAsyncStorage(): AsyncStorageLike | null {
  if (asyncStorageRef !== undefined) return asyncStorageRef;
  try {
    // Optional dependency: may not exist in constrained environments.
    const safeRequire = Function("return require")() as (name: string) => unknown;
    const mod = safeRequire("@react-native-async-storage/async-storage") as { default?: unknown };
    const candidate = (mod?.default ?? mod) as Partial<AsyncStorageLike>;
    if (
      candidate &&
      typeof candidate.getItem === "function" &&
      typeof candidate.setItem === "function"
    ) {
      asyncStorageRef = candidate as AsyncStorageLike;
      return asyncStorageRef;
    }
  } catch {
    // ignore
  }
  asyncStorageRef = null;
  return asyncStorageRef;
}

function isValidLocale(value: string | null): value is Locale {
  return value !== null && SUPPORTED_LOCALES.includes(value as Locale);
}

export async function getStoredLocale(): Promise<Locale | null> {
  try {
    const storage = getAsyncStorage();
    const value = storage
      ? await storage.getItem(LOCALE_STORAGE_KEY)
      : memoryStore.get(LOCALE_STORAGE_KEY) ?? null;
    return isValidLocale(value) ? value : null;
  } catch {
    return null;
  }
}

export async function setStoredLocale(locale: Locale): Promise<void> {
  try {
    const storage = getAsyncStorage();
    if (storage) {
      await storage.setItem(LOCALE_STORAGE_KEY, locale);
    } else {
      memoryStore.set(LOCALE_STORAGE_KEY, locale);
    }
  } catch {
    // ignore
  }
}
