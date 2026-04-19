/**
 * Client for GET /v1/config/features — the mobile app's feature-flag
 * and version-gate fetch. Called once on startup; failure is
 * non-blocking (the app falls back to sensible defaults so a backend
 * outage can't brick startup).
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";

export type EnforcementMode = "off" | "warn" | "block";

export interface ClientVersionPolicy {
  min: string;
  latest: string;
  mode: EnforcementMode;
  update_url_ios: string | null;
  update_url_android: string | null;
}

export interface FeaturesConfig {
  llm_nlu_enabled: boolean;
  llm_explain_enabled: boolean;
  client_version: ClientVersionPolicy;
}

const DEFAULT_FEATURES: FeaturesConfig = {
  llm_nlu_enabled: false,
  llm_explain_enabled: false,
  client_version: {
    min: "0.0.0",
    latest: "0.0.0",
    // Safe default: if the backend is unreachable, don't lock the
    // user out. Ops must deliberately flip "block" server-side.
    mode: "off",
    update_url_ios: null,
    update_url_android: null,
  },
};

export async function fetchFeatures(): Promise<FeaturesConfig> {
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/config/features`,
      { method: "GET", headers: { Accept: "application/json" } },
      6000,
    );
    if (!res.ok) return DEFAULT_FEATURES;
    const data = (await res.json()) as Partial<FeaturesConfig>;

    // Defensively merge so a partial payload from an older backend
    // (pre-M4, no client_version block) still produces a valid
    // FeaturesConfig. The mobile app assumes client_version is
    // always present and non-null.
    return {
      llm_nlu_enabled: Boolean(data.llm_nlu_enabled),
      llm_explain_enabled: Boolean(data.llm_explain_enabled),
      client_version: {
        ...DEFAULT_FEATURES.client_version,
        ...(data.client_version ?? {}),
      },
    };
  } catch {
    return DEFAULT_FEATURES;
  }
}
