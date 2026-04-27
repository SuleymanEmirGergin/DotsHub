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

export interface ConsentVersions {
  terms_general: string;
  health_data_processing: string;
  push_notifications: string;
  summary_email: string;
}

export interface ConsentPolicy {
  notice_version: string;
  versions: ConsentVersions;
}

export interface FeaturesConfig {
  llm_nlu_enabled: boolean;
  llm_explain_enabled: boolean;
  client_version: ClientVersionPolicy;
  consent: ConsentPolicy;
}

// Defaults match the backend's app/core/config.py defaults at the
// time of this mobile build. If /v1/config/features is unreachable
// on first launch, IntroScreen still has a usable (notice_version,
// terms_version, health_data_version) tuple to send with the
// consent rows — the next online session will refresh them. A
// version bump landed only on the backend doesn't immediately force
// re-acceptance offline; that's acceptable because the *content*
// the user agreed to didn't change in their local app bundle
// either. (Stale-consent re-prompt logic — comparing stored
// consent_records.consent_version against this `versions` block —
// is a follow-up; tracked in DPIA_2026.md mitigations.)
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
  consent: {
    notice_version: "v0.2",
    versions: {
      terms_general: "v1.0",
      health_data_processing: "v1.0",
      push_notifications: "v1.0",
      summary_email: "v1.0",
    },
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
    // (pre-M4, no client_version block; pre-session-24, no consent
    // block) still produces a valid FeaturesConfig. Older backends
    // will fall back to DEFAULT_FEATURES.consent — same hardcoded
    // versions the mobile shipped with, so behavior is unchanged.
    return {
      llm_nlu_enabled: Boolean(data.llm_nlu_enabled),
      llm_explain_enabled: Boolean(data.llm_explain_enabled),
      client_version: {
        ...DEFAULT_FEATURES.client_version,
        ...(data.client_version ?? {}),
      },
      consent: {
        notice_version:
          data.consent?.notice_version ??
          DEFAULT_FEATURES.consent.notice_version,
        versions: {
          ...DEFAULT_FEATURES.consent.versions,
          ...(data.consent?.versions ?? {}),
        },
      },
    };
  } catch {
    return DEFAULT_FEATURES;
  }
}
