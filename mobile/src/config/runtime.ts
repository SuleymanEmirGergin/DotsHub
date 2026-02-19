import Constants from "expo-constants";

type ExpoExtra = {
  API_BASE?: string;
  USE_MOCK?: string | boolean;
  PRIVACY_URL?: string;
};

const extra = (Constants.expoConfig?.extra ?? {}) as ExpoExtra;

export const API_BASE = String(extra.API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
export const USE_MOCK = String(extra.USE_MOCK ?? "false") === "true";
/** Dashboard veya statik gizlilik sayfası URL'i; boşsa uygulama içi gizlilik linki gösterilmez. */
export const PRIVACY_URL = String(extra.PRIVACY_URL ?? "").trim();

