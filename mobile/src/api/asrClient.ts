/**
 * ASR (speech-to-text) API client.
 *
 * Wraps POST /v1/asr/transcribe — multipart upload of a recorded
 * audio clip, returns the Turkish transcript. Used by the intro
 * screen and (in commit 2) per-question free-text answers to let
 * users dictate symptoms instead of typing.
 *
 * UX contract
 * -----------
 * The transcript is shown in the user_message field for the user to
 * review and edit before submission. ASR errors do NOT block the
 * user — the mobile UI falls back to typing on any failure path.
 *
 * Timeout
 * -------
 * The backend's own deadline is LLM_ASR_TIMEOUT_SECONDS (30s by
 * default). We add a small client-side margin so the AbortController
 * fires AFTER the server has had a chance to return a typed error
 * rather than racing it.
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE, USE_MOCK } from "@/src/config/runtime";
import {
  addApiBreadcrumb,
  addBreadcrumb,
} from "@/src/observability/breadcrumb";

const TIMEOUT_MS = 35000;

export type TranscribeResult = {
  transcript: string;
  remaining_today: number;
};

export type TranscribeError = {
  code:
    | "ASR_DISABLED"
    | "ASR_DAILY_LIMIT"
    | "ASR_TIMEOUT"
    | "ASR_PROVIDER_ERROR"
    | "AUDIO_TOO_LARGE"
    | "UNSUPPORTED_MEDIA"
    | "EMPTY_AUDIO"
    | "NETWORK_ERROR"
    | "UNKNOWN";
  message: string;
};

export class ASRError extends Error {
  code: TranscribeError["code"];
  constructor(code: TranscribeError["code"], message: string) {
    super(message);
    this.code = code;
    this.name = "ASRError";
  }
}

export type TranscribeInput = {
  /** Local file URI from expo-audio recorder (file://...) */
  audioUri: string;
  /** Stable per-install identifier — backend uses for daily quota. */
  device_id: string;
  /** Wiro language enum value. Default "Turkish". */
  language?: string;
  /** Best-effort MIME type. expo-audio iOS → audio/m4a; Android → audio/mp4. */
  mimeType?: string;
};

/**
 * Upload audio and receive a transcript. In USE_MOCK mode this
 * resolves to a fixed Turkish phrase so offline/demo flows aren't
 * blocked by network or provider state.
 */
export async function transcribe(
  input: TranscribeInput,
): Promise<TranscribeResult> {
  if (USE_MOCK) {
    addBreadcrumb("asr", "mock skip — returning fixed transcript", null, "info");
    return {
      transcript: "karın ağrım var ve bulantı hissediyorum",
      remaining_today: 49,
    };
  }

  addBreadcrumb(
    "asr",
    `submit intent uri=${input.audioUri.substring(0, 40)}…`,
    { language: input.language ?? "Turkish" },
    "info",
  );

  const form = new FormData();
  // React Native's FormData accepts the {uri, name, type} shape for
  // file uploads. expo-audio gives us file:// URIs directly.
  // Cast to any: TS RN typing for FormData.append doesn't model the
  // {uri,name,type} object, but the runtime accepts it.
  form.append("audio", {
    uri: input.audioUri,
    name: "clip.m4a",
    type: input.mimeType ?? "audio/m4a",
  } as any);
  form.append("device_id", input.device_id);
  form.append("language", input.language ?? "Turkish");

  const startedAt = Date.now();
  let res: Response;
  try {
    res = await fetchWithTimeout(
      `${API_BASE}/v1/asr/transcribe`,
      {
        method: "POST",
        body: form,
        // Don't set Content-Type — fetch sets multipart boundary itself.
      },
      TIMEOUT_MS,
    );
  } catch (err) {
    addApiBreadcrumb({
      endpoint: "/v1/asr/transcribe",
      method: "POST",
      status: 0,
      durationMs: Date.now() - startedAt,
      level: "error",
      note: err instanceof Error ? err.name : "network",
    });
    throw new ASRError("NETWORK_ERROR", "Bağlantı hatası");
  }

  addApiBreadcrumb({
    endpoint: "/v1/asr/transcribe",
    method: "POST",
    status: res.status,
    durationMs: Date.now() - startedAt,
    level: res.ok ? "info" : "error",
  });

  if (!res.ok) {
    let code: TranscribeError["code"] = "UNKNOWN";
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      const detail = data?.detail;
      if (detail && typeof detail === "object") {
        if (typeof detail.code === "string") code = detail.code as any;
        if (typeof detail.message === "string") message = detail.message;
      }
    } catch {
      /* non-JSON body — keep defaults */
    }
    throw new ASRError(code, message);
  }

  const data = (await res.json()) as TranscribeResult;
  if (typeof data.transcript !== "string") {
    throw new ASRError("UNKNOWN", "transcript missing in response");
  }
  return data;
}
