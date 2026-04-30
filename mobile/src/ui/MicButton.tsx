/**
 * Reusable microphone button — record → stop → upload → transcript.
 *
 * Used by:
 *   - IntroScreen (commit 1) for free-text symptom dictation
 *   - QuestionScreen / answer free-text (commit 2)
 *
 * UX states (all rendered as a single button):
 *   idle      — tap to start recording
 *   recording — tap again to stop; pulses red dot for affordance
 *   processing — uploading + waiting for backend transcript
 *   error     — short toast under the button, returns to idle
 *
 * The component never throws upward. On any failure path
 * (permission denied, recorder failure, network/provider error) it
 * surfaces a short Turkish error message and returns to idle.
 *
 * Important: voice is an *enhancement*, not a gate. Callers always
 * keep the typed text input visible and editable; this component
 * just feeds prefill text via the onTranscript callback.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  AudioModule,
  RecordingPresets,
  useAudioRecorder,
} from "expo-audio";

import { tokens } from "@/src/ui/designTokens";
import { transcribe, ASRError } from "@/src/api/asrClient";
import { useI18n } from "@/i18n/I18nProvider";
import { addBreadcrumb } from "@/src/observability/breadcrumb";

type Props = {
  /** Stable per-install identifier — backend uses for daily quota. */
  deviceId: string;
  /** Called with the transcript text on success. */
  onTranscript: (text: string) => void;
  /** Optional callback when recording starts (parent may dim other UI). */
  onRecordingChange?: (recording: boolean) => void;
  /** Optional accessibility label override. */
  accessibilityLabel?: string;
};

type Status = "idle" | "recording" | "processing" | "error";

export function MicButton({
  deviceId,
  onTranscript,
  onRecordingChange,
  accessibilityLabel,
}: Props) {
  const { t } = useI18n();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pulse = useRef(new Animated.Value(1)).current;

  // Pulse animation while recording — purely cosmetic feedback.
  useEffect(() => {
    if (status !== "recording") {
      pulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1.2,
          duration: 600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: 600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [status, pulse]);

  const surfaceError = useCallback((code: string, fallback: string) => {
    // Translate known error codes to localized strings; fall back to
    // the raw message for anything we haven't enumerated. Errors are
    // shown in-place, not via a global toast, so the user sees them
    // tied to the button they pressed.
    const map: Record<string, string> = {
      permission_denied: t("voice.errPermission"),
      ASR_DISABLED: t("voice.errDisabled"),
      ASR_DAILY_LIMIT: t("voice.errDailyLimit"),
      ASR_TIMEOUT: t("voice.errTimeout"),
      ASR_PROVIDER_ERROR: t("voice.errProvider"),
      AUDIO_TOO_LARGE: t("voice.errTooLong"),
      EMPTY_AUDIO: t("voice.errEmpty"),
      NETWORK_ERROR: t("voice.errNetwork"),
    };
    setErrorMsg(map[code] ?? fallback);
    setStatus("error");
    addBreadcrumb("asr", `mic error code=${code}`, { code }, "warning");
    // Auto-dismiss after a moment so the user can retry without
    // tapping a separate clear button.
    setTimeout(() => {
      setErrorMsg(null);
      setStatus("idle");
    }, 3500);
  }, [t]);

  const startRecording = useCallback(async () => {
    setErrorMsg(null);
    try {
      const perm = await AudioModule.requestRecordingPermissionsAsync();
      if (!perm.granted) {
        surfaceError("permission_denied", t("voice.errPermission"));
        return;
      }
      await recorder.prepareToRecordAsync();
      recorder.record();
      setStatus("recording");
      onRecordingChange?.(true);
      addBreadcrumb("asr", "recording started", null, "info");
    } catch (err) {
      addBreadcrumb(
        "asr",
        `recorder start failed: ${err instanceof Error ? err.message : String(err)}`,
        null,
        "error",
      );
      surfaceError("UNKNOWN", t("voice.errRecorder"));
    }
  }, [recorder, surfaceError, t, onRecordingChange]);

  const stopAndTranscribe = useCallback(async () => {
    setStatus("processing");
    onRecordingChange?.(false);
    let uri: string | null = null;
    try {
      await recorder.stop();
      uri = recorder.uri;
    } catch (err) {
      addBreadcrumb(
        "asr",
        `recorder stop failed: ${err instanceof Error ? err.message : String(err)}`,
        null,
        "error",
      );
      surfaceError("UNKNOWN", t("voice.errRecorder"));
      return;
    }
    if (!uri) {
      surfaceError("EMPTY_AUDIO", t("voice.errEmpty"));
      return;
    }
    try {
      const mime = Platform.OS === "ios" ? "audio/m4a" : "audio/mp4";
      const result = await transcribe({
        audioUri: uri,
        device_id: deviceId,
        mimeType: mime,
      });
      const text = result.transcript.trim();
      if (!text) {
        surfaceError("EMPTY_AUDIO", t("voice.errEmpty"));
        return;
      }
      onTranscript(text);
      setStatus("idle");
      addBreadcrumb(
        "asr",
        `transcribed chars=${text.length} remaining=${result.remaining_today}`,
        null,
        "info",
      );
    } catch (err) {
      const code = err instanceof ASRError ? err.code : "UNKNOWN";
      const msg = err instanceof Error ? err.message : "unknown";
      surfaceError(code, msg);
    }
  }, [recorder, deviceId, onTranscript, surfaceError, t, onRecordingChange]);

  const onPress = useCallback(() => {
    if (status === "idle" || status === "error") void startRecording();
    else if (status === "recording") void stopAndTranscribe();
    /* processing: ignore taps until done */
  }, [status, startRecording, stopAndTranscribe]);

  const label =
    status === "recording"
      ? t("voice.stopHint")
      : status === "processing"
        ? t("voice.processingHint")
        : t("voice.startHint");

  return (
    <View style={styles.wrap}>
      <Pressable
        onPress={onPress}
        disabled={status === "processing"}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityState={{
          busy: status === "processing",
          selected: status === "recording",
        }}
        style={({ pressed }) => [
          styles.button,
          status === "recording" && styles.buttonRecording,
          status === "processing" && styles.buttonProcessing,
          pressed && styles.buttonPressed,
        ]}
      >
        {status === "processing" ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Animated.View style={{ transform: [{ scale: pulse }] }}>
            <Text style={styles.icon}>{status === "recording" ? "■" : "🎤"}</Text>
          </Animated.View>
        )}
      </Pressable>
      <Text style={styles.label}>{label}</Text>
      {errorMsg ? (
        <Text style={styles.errorText} accessibilityRole="alert">
          {errorMsg}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: "center",
    marginVertical: tokens.spacing.sm,
  },
  button: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: tokens.colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
    elevation: 3,
  },
  buttonRecording: {
    backgroundColor: tokens.colors.error,
  },
  buttonProcessing: {
    backgroundColor: tokens.colors.textSecondary,
  },
  buttonPressed: {
    opacity: 0.85,
  },
  icon: {
    fontSize: 22,
    color: "#FFFFFF",
  },
  label: {
    ...tokens.typography.caption,
    color: tokens.colors.textSecondary,
    marginTop: tokens.spacing.xs,
  },
  errorText: {
    ...tokens.typography.caption,
    color: tokens.colors.error,
    marginTop: tokens.spacing.xs,
    maxWidth: 240,
    textAlign: "center",
  },
});
