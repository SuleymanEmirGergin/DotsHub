import React, { useState } from "react";
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

const LOADING_TEXT = "Değerlendiriyorum…";

export default function QuestionScreen() {
  const q = useTriageStore((s) => s.pendingQuestion)!;
  const sessionId = useTriageStore((s) => s.sessionId);
  const { appendMessage, setLoading, applyEnvelope } = useTriageStore();

  const [freeText, setFreeText] = useState("");

  async function answer(value: string) {
    appendMessage({
      role: "user",
      text: value === "yes" ? "Evet" : value === "no" ? "Hayır" : value,
    });
    setLoading(true);
    appendMessage({ role: "assistant", text: LOADING_TEXT });

    const env = await triageTurn({
      session_id: sessionId,
      locale: "tr-TR",
      user_message: "",
      answer: { canonical: q.canonical, value },
    });
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
              <Text style={styles.whyLabel}>Neden soruyoruz?</Text>
              <MutedText style={styles.whyText}>{q.why_asking_tr}</MutedText>
            </View>
          ) : null}

          {q.answer_type === "yes_no" ? (
            <View style={styles.yesNoRow}>
              <PrimaryButton style={styles.flexButton} onPress={() => answer("yes")}>
                Evet
              </PrimaryButton>
              <SecondaryButton style={styles.flexButton} onPress={() => answer("no")}>
                Hayır
              </SecondaryButton>
            </View>
          ) : null}

          {q.answer_type === "free_text" ? (
            <View style={styles.freeTextBox}>
              <TextInput
                value={freeText}
                onChangeText={setFreeText}
                placeholder="Kısa yanıt yaz…"
                placeholderTextColor={tokens.colors.textMuted}
                style={[styles.freeInput, styles.freeInputMultiline]}
                multiline
                textAlignVertical="top"
              />
              <PrimaryButton
                style={styles.continueButton}
                onPress={() => answer(freeText.trim() || "bilmiyorum")}
              >
                Devam
              </PrimaryButton>
            </View>
          ) : null}

          {q.answer_type === "number" ? (
            <View style={styles.freeTextBox}>
              <TextInput
                value={freeText}
                onChangeText={setFreeText}
                placeholder="Sayı gir…"
                placeholderTextColor={tokens.colors.textMuted}
                keyboardType="numeric"
                style={styles.freeInput}
              />
              <PrimaryButton
                style={styles.continueButton}
                onPress={() => answer(freeText.trim() || "0")}
              >
                Devam
              </PrimaryButton>
            </View>
          ) : null}

          {q.answer_type === "multi_choice" && q.choices_tr ? (
            <View style={styles.choicesCol}>
              {q.choices_tr.map((choice) => (
                <Pressable
                  key={choice}
                  onPress={() => answer(choice)}
                  style={({ pressed }) => [
                    styles.choiceButton,
                    pressed ? styles.choiceButtonPressed : null,
                  ]}
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
