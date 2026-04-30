import React, { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { triageTurn } from "@/src/api/triageClient";
import { useTriageStore } from "@/src/state/triageStore";
import { inputHeights, tokens } from "@/src/ui/designTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
  SectionTitle,
} from "@/src/ui/primitives";
import { useI18n } from "@/i18n/I18nProvider";
import { MicButton } from "@/src/ui/MicButton";
import { getDeviceId } from "@/utils/deviceId";
import { fetchFeatures } from "@/src/api/featuresClient";

export default function QuestionScreen() {
  const { t } = useI18n();
  const q = useTriageStore((s) => s.pendingQuestion)!;
  const sessionId = useTriageStore((s) => s.sessionId);
  const { appendMessage, setLoading, setLastRequest, applyEnvelope } = useTriageStore();

  const [freeText, setFreeText] = useState("");
  const [asrEnabled, setAsrEnabled] = useState(false);
  const deviceId = useMemo(() => getDeviceId(), []);

  // Re-fetch /features each time we land on a free-text question.
  // Cheap (cached/204-friendly) and lets ops flip the asr flag mid-
  // session without a forced relaunch. No-op for yes_no/multi_choice
  // because the MicButton render is gated on answer_type below
  // anyway — this just means we never show a stale "mic available"
  // affordance if ops just turned the feature off.
  useEffect(() => {
    let cancelled = false;
    if (q.answer_type !== "free_text") return;
    fetchFeatures().then((f) => {
      if (!cancelled) setAsrEnabled(Boolean(f.asr_enabled));
    });
    return () => { cancelled = true; };
  }, [q.answer_type]);

  async function answer(value: string) {
    const req = {
      session_id: sessionId,
      locale: "tr-TR" as const,
      user_message: "",
      answer: { canonical: q.canonical, value },
    };
    appendMessage({
      role: "user",
      text: value === "yes" ? "Evet" : value === "no" ? "Hayır" : value,
    });
    setLoading(true);
    setLastRequest(req);
    appendMessage({ role: "assistant", text: t("chat.evaluating") });

    const env = await triageTurn(req);
    applyEnvelope(env);
  }

  return (
    <ScreenContainer>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <Card>
          <SectionTitle style={styles.questionText}>{q.question_tr}</SectionTitle>

          {q.why_asking_tr ? (
            <View style={styles.whyBox}>
              <Text style={styles.whyLabel}>{t("question.whyAsking")}</Text>
              <MutedText style={styles.whyText}>{q.why_asking_tr}</MutedText>
            </View>
          ) : null}

          {q.answer_type === "yes_no" ? (
            <View style={styles.yesNoRow}>
              <PrimaryButton style={styles.flexButton} onPress={() => answer("yes")}>
                {t("common.yes")}
              </PrimaryButton>
              <SecondaryButton style={styles.flexButton} onPress={() => answer("no")}>
                {t("common.no")}
              </SecondaryButton>
            </View>
          ) : null}

          {q.answer_type === "free_text" ? (
            <View style={styles.freeTextBox}>
              <TextInput
                value={freeText}
                onChangeText={setFreeText}
                placeholder={t("question.freeTextPlaceholder")}
                placeholderTextColor={tokens.colors.textMuted}
                style={[styles.freeInput, styles.freeInputMultiline]}
                multiline
                textAlignVertical="top"
                accessibilityLabel={t("question.freeTextInputLabel")}
                accessibilityHint={t("question.freeTextInputHint")}
              />
              {asrEnabled ? (
                // Mic only appears under free-text answers — yes_no /
                // number / multi_choice don't need dictation. Same
                // append-not-replace behavior as ChatScreen so a
                // partial typed start survives the dictation.
                <MicButton
                  deviceId={deviceId}
                  onTranscript={(transcript) => {
                    setFreeText((prev) => (prev.trim()
                      ? prev.trim() + " " + transcript
                      : transcript));
                  }}
                />
              ) : null}
              <PrimaryButton
                style={styles.continueButton}
                onPress={() => answer(freeText.trim() || "bilmiyorum")}
              >
                {t("common.continue")}
              </PrimaryButton>
            </View>
          ) : null}

          {q.answer_type === "number" ? (
            <View style={styles.freeTextBox}>
              <TextInput
                value={freeText}
                onChangeText={setFreeText}
                placeholder={t("question.numberPlaceholder")}
                placeholderTextColor={tokens.colors.textMuted}
                keyboardType="numeric"
                style={styles.freeInput}
                accessibilityLabel={t("question.numberInputLabel")}
                accessibilityHint={t("question.numberInputHint")}
              />
              <PrimaryButton
                style={styles.continueButton}
                onPress={() => answer(freeText.trim() || "0")}
              >
                {t("common.continue")}
              </PrimaryButton>
            </View>
          ) : null}

          {q.answer_type === "multi_choice" && q.choices_tr ? (
            <View
              style={styles.choicesCol}
              // Native "radio group" role helps VoiceOver/TalkBack
              // navigate choices as a cohesive set rather than
              // individual buttons scattered on screen.
              accessibilityRole="radiogroup"
              accessibilityLabel={t("question.choiceOption")}
            >
              {q.choices_tr.map((choice) => (
                <Pressable
                  key={choice}
                  onPress={() => answer(choice)}
                  style={({ pressed }) => [
                    styles.choiceButton,
                    pressed ? styles.choiceButtonPressed : null,
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel={`${t("question.choiceOption")}: ${choice}`}
                >
                  <Text style={styles.choiceButtonText}>{choice}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </Card>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingVertical: tokens.spacing.lg,
  },
  questionText: {
    marginBottom: tokens.spacing.md,
    fontSize: tokens.typography.h1.fontSize,
    lineHeight: tokens.typography.h1.lineHeight,
  },
  whyBox: {
    backgroundColor: tokens.colors.surfaceAlt,
    borderRadius: tokens.radius.md,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    padding: tokens.spacing.md,
    marginBottom: tokens.spacing.lg,
  },
  whyLabel: {
    ...tokens.typography.caption,
    color: tokens.colors.textSecondary,
    fontWeight: "700",
    marginBottom: tokens.spacing.xs,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  whyText: {
    color: tokens.colors.textSecondary,
  },
  yesNoRow: {
    flexDirection: "row",
    gap: tokens.spacing.sm,
  },
  flexButton: {
    flex: 1,
  },
  freeTextBox: {
    marginTop: tokens.spacing.xs,
  },
  freeInput: {
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
  freeInputMultiline: {
    minHeight: 88,
  },
  continueButton: {
    marginTop: tokens.spacing.sm,
  },
  choicesCol: {
    gap: tokens.spacing.sm,
  },
  choiceButton: {
    minHeight: inputHeights.md,
    borderRadius: tokens.radius.md,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    backgroundColor: tokens.colors.surfaceAlt,
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
  },
  choiceButtonPressed: {
    opacity: 0.9,
  },
  choiceButtonText: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    fontWeight: "600",
    textAlign: "center",
  },
});
