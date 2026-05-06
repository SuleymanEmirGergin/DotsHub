/**
 * ASR (automatic speech recognition) API client.
 *
 * Wraps `POST /v1/asr/transcribe`. The endpoint accepts a multipart
 * upload with an `audio` part (m4a from `utils/voice.ts`) plus a
 * `language` field. It returns the transcript text plus some metadata
 * (provider, model, duration) we surface for debug logs but don't
 * render in the UI.
 *
 * The client uses `fetchWithTimeout` so a stuck server doesn't
 * indefinitely block the recording state — if the upload exceeds
 * `30s` we fail and the screen restores idle state. The default
 * 12s in `fetchWithTimeout` is too tight here because Whisper round
 * trips can run 5-15s on top of the upload itself.
 */

import { fetchWithTimeout } from "./fetchWithTimeout";
import { API_BASE } from "@/src/config/runtime";
import {
  addApiBreadcrumb,
  addBreadcrumb,
} from "@/src/observability/breadcrumb";

export interface TranscriptionResult {
  text: string;
  language: string;
  provider: string;
  model?: string | null;
  duration_ms?: number | null;
}

export async function transcribeAudio(
  uri: string,
  opts: {
    filename?: string;
    contentType?: string;
    language?: string;
  } = {},
): Promise<TranscriptionResult> {
  const filename = opts.filename ?? "recording.m4a";
  const contentType = opts.contentType ?? "audio/m4a";
  const language = opts.language ?? "tr";

  // FormData on RN takes the `{ uri, name, type }` shape; TS can't
  // express this overload natively so we widen via `as any`.
  const form = new FormData();
  form.append("audio", {
    uri,
    name: filename,
    type: contentType,
  } as unknown as Blob);
  form.append("language", language);

  addBreadcrumb(
    "asr",
    `transcribe begin lang=${language}`,
    { language },
    "info",
  );

  const startedAt = Date.now();
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/asr/transcribe`,
      {
        method: "POST",
        body: form,
        // Note: do NOT set Content-Type ourselves — the runtime's
        // FormData polyfill picks the correct multipart boundary.
        // Setting it manually breaks the upload on Android.
      },
      30000,
    );
    addApiBreadcrumb({
      endpoint: "/v1/asr/transcribe",
      method: "POST",
      status: res.status,
      durationMs: Date.now() - startedAt,
      level: res.ok ? "info" : "error",
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      const message =
        detail?.detail?.message_tr ||
        (typeof detail?.detail === "string" ? detail.detail : null) ||
        `HTTP ${res.status}`;
      throw new Error(message);
    }
    return (await res.json()) as TranscriptionResult;
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("HTTP ")) {
      throw err;
    }
    addApiBreadcrumb({
      endpoint: "/v1/asr/transcribe",
      method: "POST",
      status: 0,
      durationMs: Date.now() - startedAt,
      level: "error",
      note: err instanceof Error ? err.name : "network",
    });
    throw err;
  }
}
