import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { transcribeAudio } from "@/src/api/asrClient";
import { triageTurn } from "@/src/api/triageClient";
import { useTriageStore } from "@/src/state/triageStore";
import { inputHeights, touchTargetMin } from "@/src/ui/designTokens";
import { useTokens } from "@/src/ui/useTokens";
import {
  Badge,
  Card,
  MutedText,
  ScreenContainer,
  SectionTitle,
} from "@/src/ui/primitives";
import { useI18n } from "@/i18n/I18nProvider";
import {
  abortVoiceCapture,
  beginVoiceCapture,
  endVoiceCapture,
  type VoiceSession,
} from "@/utils/voice";

const QUICK_CHIPS = [
  "Baş ağrısı",
  "Ateş",
  "Öksürük",
  "Karın ağrısı",
  "İdrar yanması",
];

// Whisper handles ~30s well, ~60s acceptably. Beyond that latency + cost
// climb without much accuracy gain, and a forgotten mic shouldn't run
// the device's audio session forever. We auto-stop at this deadline.
const MAX_RECORDING_MS = 60_000;

type VoiceState = "idle" | "recording" | "transcribing";

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default function ChatScreen() {
  const [text, setText] = useState("");
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [voiceDuration, setVoiceDuration] = useState(0);
  const sessionRef = useRef<VoiceSession | null>(null);
  const flatListRef = useRef<FlatList>(null);
  const { t } = useI18n();
  const tokens = useTokens();
  const {
    sessionId,
    messages,
    loading,
    appendMessage,
    setLoading,
    setLastRequest,
    applyEnvelope,
  } = useTriageStore();
  const setShowHistory = useTriageStore((s) => s.setShowHistory);
  const setShowSettings = useTriageStore((s) => s.setShowSettings);

  // Stable callback so the auto-stop timer effect doesn't re-fire on
  // every render. setText is stable via useState; we don't depend on
  // anything else, so the [] deps are correct.
  const stopAndTranscribe = useCallback(async () => {
    const session = sessionRef.current;
    sessionRef.current = null;
    if (!session) {
      setVoiceState("idle");
      return;
    }
    setVoiceState("transcribing");
    try {
      const uri = await endVoiceCapture(session);
      const result = await transcribeAudio(uri);
      const transcript = result.text.trim();
      if (transcript.length > 0) {
        setText((prev) => {
          const trimmedPrev = prev.trim();
          return trimmedPrev.length === 0
            ? transcript
            : `${trimmedPrev} ${transcript}`;
        });
      }
    } catch (err) {
      Alert.alert(
        t("chat.voiceErrorTitle"),
        err instanceof Error && err.message
          ? err.message
          : t("chat.voiceErrorBody"),
      );
    } finally {
      setVoiceState("idle");
      setVoiceDuration(0);
    }
  }, [t]);

  // Tick the duration every 250ms while recording, and auto-fire the
  // stop+transcribe path when we hit MAX_RECORDING_MS so the user doesn't
  // accidentally upload a 10-minute audio clip if their phone goes quiet.
  useEffect(() => {
    if (voiceState !== "recording" || !sessionRef.current) return;
    const session = sessionRef.current;
    let cancelled = false;
    const tick = () => {
      if (cancelled) return;
      const elapsed = Date.now() - session.startedAt;
      setVoiceDuration(elapsed);
      if (elapsed >= MAX_RECORDING_MS) {
        cancelled = true;
        clearInterval(id);
        stopAndTranscribe().catch(() => {});
      }
    };
    tick();
    const id = setInterval(tick, 250);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [voiceState, stopAndTranscribe]);

  // If the screen unmounts mid-recording (user navigates back, app
  // backgrounds, etc.), release the audio session so we don't leave
  // the mic indicator hanging on iOS.
  useEffect(() => {
    return () => {
      if (sessionRef.current) {
        abortVoiceCapture(sessionRef.current).catch(() => {});
        sessionRef.current = null;
      }
    };
  }, []);

  async function handleMicPress() {
    if (voiceState === "transcribing") return;
    if (voiceState === "recording") {
      await stopAndTranscribe();
      return;
    }
    // idle → start a new recording.
    try {
      const session = await beginVoiceCapture();
      if (!session) {
        Alert.alert(
          t("chat.voicePermissionTitle"),
          t("chat.voicePermissionBody"),
        );
        return;
      }
      sessionRef.current = session;
      setVoiceDuration(0);
      setVoiceState("recording");
    } catch (err) {
      Alert.alert(
        t("chat.voiceErrorTitle"),
        err instanceof Error && err.message
          ? err.message
          : t("chat.voiceErrorBody"),
      );
    }
  }

  async function onSend(msg?: string) {
    const trimmed = (msg || text).trim();
    if (!trimmed) return;

    const req = {
      session_id: sessionId,
      locale: "tr-TR" as const,
      user_message: trimmed,
      answer: null,
    };
    appendMessage({ role: "user", text: trimmed });
    setText("");
    setLoading(true);
    setLastRequest(req);
    appendMessage({ role: "assistant", text: t("chat.evaluating") });

    const env = await triageTurn(req);
    applyEnvelope(env);
  }

  const styles = useMemo(
    () =>
      StyleSheet.create({
        flex: {
          flex: 1,
        },
        headerWrap: {
          marginTop: tokens.spacing.lg,
          marginBottom: tokens.spacing.md,
        },
        headerRow: {
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        },
        headerTitle: {
          marginBottom: tokens.spacing.xs,
        },
        headerActions: {
          flexDirection: "row",
          gap: tokens.spacing.xs,
        },
        historyBtn: {
          paddingHorizontal: tokens.spacing.md,
          paddingVertical: tokens.spacing.xs,
          borderRadius: tokens.radius.pill,
          backgroundColor: tokens.colors.surfaceAlt,
          borderWidth: 1,
          borderColor: tokens.colors.border,
        },
        historyBtnText: {
          ...tokens.typography.caption,
          fontWeight: "600",
          color: tokens.colors.textSecondary,
        },
        list: {
          flex: 1,
        },
        listContent: {
          paddingBottom: tokens.spacing.md,
        },
        bubble: {
          maxWidth: "86%",
          marginVertical: tokens.spacing.xs,
          paddingHorizontal: tokens.spacing.md,
          paddingVertical: tokens.spacing.sm,
          borderRadius: tokens.radius.lg,
          borderWidth: 1,
        },
        bubbleUser: {
          alignSelf: "flex-end",
          backgroundColor: tokens.colors.primary,
          borderColor: tokens.colors.primary,
        },
        bubbleAssistant: {
          alignSelf: "flex-start",
          backgroundColor: tokens.colors.surface,
          borderColor: tokens.colors.border,
        },
        bubbleText: {
          ...tokens.typography.body,
        },
        bubbleTextUser: {
          color: "#FFFFFF",
        },
        bubbleTextAssistant: {
          color: tokens.colors.textPrimary,
        },
        chipsRow: {
          flexDirection: "row",
          flexWrap: "wrap",
          gap: tokens.spacing.sm,
          marginBottom: tokens.spacing.md,
        },
        chip: {
          paddingVertical: 0,
          paddingHorizontal: 0,
          borderRadius: tokens.radius.pill,
          backgroundColor: tokens.colors.surface,
          borderColor: tokens.colors.border,
        },
        chipPressable: {
          minHeight: touchTargetMin,
          minWidth: 64,
          alignItems: "center",
          justifyContent: "center",
          paddingHorizontal: tokens.spacing.md,
          paddingVertical: tokens.spacing.xs,
        },
        chipText: {
          ...tokens.typography.bodySmall,
          color: tokens.colors.textSecondary,
          fontWeight: "600",
        },
        inputCard: {
          padding: tokens.spacing.sm,
          borderRadius: tokens.radius.lg,
          marginBottom: tokens.spacing.sm,
          ...tokens.shadow.soft,
        },
        inputRow: {
          flexDirection: "row",
          alignItems: "center",
          gap: tokens.spacing.sm,
        },
        input: {
          flex: 1,
          minHeight: inputHeights.md,
          borderWidth: 1,
          borderColor: tokens.colors.border,
          borderRadius: tokens.radius.md,
          paddingHorizontal: tokens.spacing.md,
          paddingVertical: tokens.spacing.sm,
          backgroundColor: tokens.colors.surface,
          color: tokens.colors.textPrimary,
          ...tokens.typography.body,
        },
        sendBtn: {
          minHeight: inputHeights.md,
          minWidth: 90,
          borderRadius: tokens.radius.md,
          backgroundColor: tokens.colors.primary,
          paddingHorizontal: tokens.spacing.md,
          alignItems: "center",
          justifyContent: "center",
        },
        sendBtnDisabled: {
          opacity: 0.4,
        },
        sendBtnText: {
          ...tokens.typography.button,
        },
        micBtn: {
          minHeight: inputHeights.md,
          minWidth: inputHeights.md,
          borderRadius: tokens.radius.md,
          alignItems: "center",
          justifyContent: "center",
          paddingHorizontal: tokens.spacing.sm,
          flexDirection: "row",
          gap: tokens.spacing.xs,
        },
        micBtnIdle: {
          backgroundColor: tokens.colors.surfaceAlt,
          borderWidth: 1,
          borderColor: tokens.colors.border,
        },
        micBtnRecording: {
          backgroundColor: tokens.colors.error,
        },
        micBtnTranscribing: {
          backgroundColor: tokens.colors.surfaceAlt,
          opacity: 0.6,
        },
        micGlyphIdle: {
          fontSize: 20,
          lineHeight: 22,
          color: tokens.colors.textPrimary,
        },
        micGlyphRecording: {
          color: "#FFFFFF",
          fontSize: 14,
          fontWeight: "700",
        },
        micTimer: {
          ...tokens.typography.caption,
          color: "#FFFFFF",
          fontWeight: "600",
        },
        micBusyLabel: {
          ...tokens.typography.caption,
          color: tokens.colors.textSecondary,
        },
        disclaimer: {
          textAlign: "center",
          marginBottom: tokens.spacing.md,
        },
        locationHint: {
          marginTop: tokens.spacing.xs,
          fontSize: 12,
          fontStyle: "italic",
        },
      }),
    [tokens],
  );

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? 12 : 0}
    >
      <ScreenContainer style={styles.flex}>
        <View style={styles.headerWrap}>
          <View style={styles.headerRow}>
            <SectionTitle style={styles.headerTitle}>
              {t("chat.title")}
            </SectionTitle>
            <View style={styles.headerActions}>
              <Pressable
                onPress={() => setShowHistory(true)}
                style={styles.historyBtn}
                accessibilityRole="button"
                accessibilityLabel={t("chat.history")}
              >
                <Text style={styles.historyBtnText}>{t("chat.history")}</Text>
              </Pressable>
              <Pressable
                onPress={() => setShowSettings(true)}
                style={styles.historyBtn}
                accessibilityRole="button"
                accessibilityLabel={t("chat.settings")}
              >
                <Text style={styles.historyBtnText}>{t("chat.settings")}</Text>
              </Pressable>
            </View>
          </View>
          <MutedText>{t("chat.subtitle")}</MutedText>
          <MutedText style={styles.locationHint}>
            {t("chat.locationHint")}
          </MutedText>
        </View>

        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(_, i) => String(i)}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          onContentSizeChange={() =>
            flatListRef.current?.scrollToEnd({ animated: true })
          }
          // Announce new messages to screen readers politely (doesn't
          // interrupt current speech). The FlatList itself doesn't
          // need a role — each bubble below is marked as text.
          accessibilityLiveRegion="polite"
          renderItem={({ item }) => {
            const fromUser = item.role === "user";
            const speakerLabel = fromUser
              ? t("chat.bubbleUser")
              : t("chat.bubbleAssistant");
            return (
              <View
                style={[
                  styles.bubble,
                  fromUser ? styles.bubbleUser : styles.bubbleAssistant,
                ]}
                // "You: Baş ağrım var" / "Assistant: Ne zaman başladı?"
                // — the screen reader reads this combined string so
                // the user always knows who just spoke.
                accessible
                accessibilityRole="text"
                accessibilityLabel={`${speakerLabel}: ${item.text}`}
              >
                <Text
                  style={[
                    styles.bubbleText,
                    fromUser ? styles.bubbleTextUser : styles.bubbleTextAssistant,
                  ]}
                >
                  {item.text}
                </Text>
              </View>
            );
          }}
        />

        {messages.length === 0 ? (
          <View style={styles.chipsRow}>
            {QUICK_CHIPS.map((chip) => (
              <Badge key={chip} style={styles.chip}>
                <Pressable
                  onPress={() => onSend(chip)}
                  style={styles.chipPressable}
                  hitSlop={6}
                  accessibilityRole="button"
                  accessibilityLabel={`${t("chat.quickChip")}: ${chip}`}
                >
                  <Text style={styles.chipText}>{chip}</Text>
                </Pressable>
              </Badge>
            ))}
          </View>
        ) : null}

        <Card style={styles.inputCard}>
          <View style={styles.inputRow}>
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder="Belirtini yaz…"
              placeholderTextColor={tokens.colors.textMuted}
              style={styles.input}
              editable={!loading && voiceState === "idle"}
              onSubmitEditing={() => onSend()}
              returnKeyType="send"
              accessibilityLabel={t("chat.symptomInput")}
              accessibilityHint={t("chat.symptomInputHint")}
            />
            <Pressable
              onPress={handleMicPress}
              disabled={loading || voiceState === "transcribing"}
              style={[
                styles.micBtn,
                voiceState === "idle" && styles.micBtnIdle,
                voiceState === "recording" && styles.micBtnRecording,
                voiceState === "transcribing" && styles.micBtnTranscribing,
              ]}
              accessibilityRole="button"
              accessibilityLabel={
                voiceState === "recording"
                  ? t("chat.voiceStopLabel")
                  : t("chat.voiceStartLabel")
              }
              accessibilityState={{
                disabled: loading || voiceState === "transcribing",
              }}
            >
              {voiceState === "recording" ? (
                <>
                  <Text style={styles.micGlyphRecording}>■</Text>
                  <Text style={styles.micTimer}>
                    {formatDuration(voiceDuration)}
                  </Text>
                </>
              ) : voiceState === "transcribing" ? (
                <Text style={styles.micBusyLabel}>{t("chat.voiceBusy")}</Text>
              ) : (
                <Text style={styles.micGlyphIdle}>🎤</Text>
              )}
            </Pressable>
            <Pressable
              onPress={() => onSend()}
              disabled={loading || !text.trim() || voiceState !== "idle"}
              style={[
                styles.sendBtn,
                (loading || !text.trim() || voiceState !== "idle") &&
                  styles.sendBtnDisabled,
              ]}
              accessibilityRole="button"
              accessibilityLabel={t("common.next")}
              accessibilityState={{
                disabled: loading || !text.trim() || voiceState !== "idle",
              }}
            >
              <Text style={styles.sendBtnText}>{t("chat.send")}</Text>
            </Pressable>
          </View>
        </Card>

        <MutedText style={styles.disclaimer}>
          {t("chat.emergencyDisclaimer")}
        </MutedText>
      </ScreenContainer>
    </KeyboardAvoidingView>
  );
}
