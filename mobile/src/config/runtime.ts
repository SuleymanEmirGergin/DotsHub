import Constants from "expo-constants";

type ExpoExtra = {
  API_BASE?: string;
  USE_MOCK?: string | boolean;
};

const extra = (Constants.expoConfig?.extra ?? {}) as ExpoExtra;

export const API_BASE = String(extra.API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
export const USE_MOCK = String(extra.USE_MOCK ?? "false") === "true";

