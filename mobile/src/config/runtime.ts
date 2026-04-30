import Constants from "expo-constants";

type ExpoExtra = {
  API_BASE?: string;
  USE_MOCK?: string | boolean;
  PRIVACY_URL?: string;
};

const extra = (Constants.expoConfig?.extra ?? {}) as ExpoExtra;

// Default to the prod Fly backend (matches .env.example) so a fresh
// clone with no .env still reaches a working API from a real device.
// Override locally with API_BASE in mobile/.env when developing
// against a laptop backend (e.g. http://<lan-ip>:8000).
export const API_BASE = String(extra.API_BASE ?? "https://triaige-backend.fly.dev").replace(/\/+$/, "");
export const USE_MOCK = String(extra.USE_MOCK ?? "false") === "true";
/** Dashboard veya statik gizlilik sayfası URL'i; boşsa uygulama içi gizlilik linki gösterilmez. */
export const PRIVACY_URL = String(extra.PRIVACY_URL ?? "").trim();

