/**
 * Voice capture helper for the chat textarea.
 *
 * Wraps expo-av's `Audio.Recording` API behind a tiny "session" object
 * so screens don't have to dance with audio-mode setup, permission
 * negotiation, and clean-up. The recorded file is m4a (HIGH_QUALITY
 * preset) on both iOS and Android so the backend's `/v1/asr/transcribe`
 * endpoint sees a single MIME shape regardless of platform.
 *
 * Usage from a screen:
 *
 *   const session = await beginVoiceCapture();
 *   if (!session) {
 *     // Permission denied — fall back to typing.
 *   }
 *   // … user taps stop:
 *   const uri = await endVoiceCapture(session);
 *   const { text } = await transcribeAudio(uri);
 *
 * The `MAX_RECORDING_MS` cap is enforced at the call site (the screen
 * starts a timer when it begins; auto-fires `endVoiceCapture` at the
 * deadline). This module stays state-free so it can be reused for
 * future flows (e.g. Q-and-A free_text answers) without coupling them
 * to the chat screen's timer.
 */

import { Audio } from "expo-av";

export interface VoiceSession {
  recording: Audio.Recording;
  startedAt: number;
}

/**
 * Begin a recording. Returns null if the user denies microphone
 * permission — the screen should fall back to typed input in that
 * case (and may surface an Alert pointing them to system settings).
 */
export async function beginVoiceCapture(): Promise<VoiceSession | null> {
  const perm = await Audio.requestPermissionsAsync();
  if (perm.status !== "granted") return null;

  // Configure audio mode so iOS lets us record (the default mode
  // silences recording while the device is on Silent). The mode
  // persists for the lifetime of the screen — we restore the
  // playback-friendly settings inside `endVoiceCapture` /
  // `abortVoiceCapture` so subsequent `Linking.openURL("tel:…")`
  // calls aren't routed through the recording-only mode.
  await Audio.setAudioModeAsync({
    allowsRecordingIOS: true,
    playsInSilentModeIOS: true,
    staysActiveInBackground: false,
    shouldDuckAndroid: true,
  });

  const recording = new Audio.Recording();
  await recording.prepareToRecordAsync(
    Audio.RecordingOptionsPresets.HIGH_QUALITY,
  );
  await recording.startAsync();
  return { recording, startedAt: Date.now() };
}

/**
 * Stop the recording and return the local file URI. Throws if the
 * file system fails to flush — callers should surface this as a
 * "ses kaydı tamamlanamadı, lütfen tekrar deneyin" message.
 */
export async function endVoiceCapture(session: VoiceSession): Promise<string> {
  await session.recording.stopAndUnloadAsync();
  const uri = session.recording.getURI();
  if (!uri) {
    throw new Error("Recording produced no file");
  }
  await Audio.setAudioModeAsync({
    allowsRecordingIOS: false,
    playsInSilentModeIOS: false,
  }).catch(() => {});
  return uri;
}

/**
 * Cancel a recording without uploading anything. Useful when the
 * user navigates away mid-recording, the screen unmounts, or we
 * hit an error path before the upload step.
 */
export async function abortVoiceCapture(session: VoiceSession): Promise<void> {
  try {
    await session.recording.stopAndUnloadAsync();
  } catch {
    // Already stopped — fine.
  }
  await Audio.setAudioModeAsync({
    allowsRecordingIOS: false,
    playsInSilentModeIOS: false,
  }).catch(() => {});
}
