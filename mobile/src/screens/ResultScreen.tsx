import React, { useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { sendFeedback } from "@/src/api/feedbackClient";
import { sendSummaryEmail, exportSummary } from "@/src/api/summaryClient";
import { useTriageStore } from "@/src/state/triageStore";
import { computeConfidence } from "@/src/state/confidence";
import { inputHeights, tokens } from "@/src/ui/designTokens";
import {
  Badge,
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
  SectionTitle,
} from "@/src/ui/primitives";
import ConfidenceBar from "@/src/ui/ConfidenceBar";
import { usePushRegistration } from "@/src/hooks/usePushRegistration";
import { unregisterPushTokenIfNeeded } from "@/src/api/pushClient";
import { buildSummaryHtml, shareSummaryAsPdf } from "@/utils/sharePdf";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";

export default function ResultScreen() {
  const { t, isRTL, locale } = useI18n();
  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;
  const result = useTriageStore((s) => s.result)!;
  const sessionId = useTriageStore((s) => s.sessionId);
  const resetSession = useTriageStore((s) => s.resetSession);

  usePushRegistration(locale);

  // Backend accepts tr | en | de | ru | ar and normalizes content (de/ru/ar -> tr)

  // Use backend confidence if available, otherwise compute locally
  const backendConf = result.confidence_0_1;
  const localConf = computeConfidence(result);
  const confidence = backendConf ?? localConf.confidence;
  const label = result.confidence_label_tr ?? localConf.label;
  const hint = result.confidence_explain_tr ?? localConf.hint;

  const summaryText = result.doctor_ready_summary_tr.join("\n");

  // Feedback state
  const [fbMode, setFbMode] = useState<null | "up" | "down">(null);
  const [fbSent, setFbSent] = useState(false);
  const [comment, setComment] = useState("");

  const [sharingPdf, setSharingPdf] = useState(false);
  const [email, setEmail] = useState("");
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const [downloadingText, setDownloadingText] = useState(false);
  const disclaimer = t("result.disclaimer");

  async function onShareSummary() {
    try {
      await Share.share({
        message: summaryText + "\n\n" + disclaimer,
        title: t("result.shareTitle"),
      });
    } catch {
      Alert.alert(t("result.alertError"), t("result.shareError"));
    }
  }

  async function onSendEmail() {
    const trimmed = email.trim();
    if (!sessionId || !trimmed || sendingEmail || emailSent) return;
    setSendingEmail(true);
    try {
      await sendSummaryEmail(sessionId, trimmed, locale);
      setEmailSent(true);
      Alert.alert(t("common.ok"), t("result.emailSent"));
    } catch (e) {
      Alert.alert(t("common.error"), t("result.emailError") + " " + (e instanceof Error ? e.message : ""));
    } finally {
      setSendingEmail(false);
    }
  }

  async function onDownloadText() {
    if (downloadingText) return;
    setDownloadingText(true);
    try {
      const text = await exportSummary(result, locale === "en" ? "en" : "tr-TR");
      const canShareFile = await Sharing.isAvailableAsync();
      if (canShareFile && FileSystem.cacheDirectory) {
        const dateStr = new Date().toISOString().slice(0, 10);
        const filename = `triyaj-ozeti-${dateStr}.txt`;
        const path = FileSystem.cacheDirectory + filename;
        await FileSystem.writeAsStringAsync(path, text, { encoding: FileSystem.EncodingType.UTF8 });
        try {
          await Sharing.shareAsync(path, {
            mimeType: "text/plain",
            dialogTitle: t("result.shareTitle"),
          });
        } finally {
          await FileSystem.deleteAsync(path, { idempotent: true });
        }
      } else {
        await Share.share({
          message: text,
          title: t("result.shareTitle"),
        });
      }
    } catch (e) {
      Alert.alert(t("common.error"), t("result.downloadError") + " " + (e instanceof Error ? e.message : ""));
    } finally {
      setDownloadingText(false);
    }
  }

  async function onSharePdf() {
    setSharingPdf(true);
    try {
      const html = buildSummaryHtml({
        title: t("result.pdfTitle"),
        specialty: result.recommended_specialty.name_tr,
        urgency:
          result.urgency === "ROUTINE"
            ? t("result.urgencyRoutine")
            : result.urgency === "SAME_DAY"
              ? t("result.urgencySameDay")
              : t("result.urgencyAcil"),
        rationale: Array.isArray(result.why_specialty_tr) ? result.why_specialty_tr : undefined,
        candidates: result.top_conditions.map((c) => ({
          label: c.disease_label,
          probability: c.score_0_1,
        })),
        summaryLines: result.doctor_ready_summary_tr,
        disclaimer,
      });
      const ok = await shareSummaryAsPdf(html, onShareSummary);
      if (!ok) Alert.alert(t("result.alertInfo"), t("result.pdfNotSupported"));
    } catch {
      Alert.alert(t("result.alertError"), t("result.pdfError"));
    } finally {
      setSharingPdf(false);
    }
  }

  async function submitFeedback(rating: "up" | "down") {
    if (!sessionId || fbSent) return;
    try {
      await sendFeedback({
        session_id: sessionId,
        rating,
        comment: rating === "down" ? comment.trim() || null : null,
        user_selected_specialty_id: null,
      });
      Alert.alert(t("result.feedbackThanksTitle"), t("result.feedbackThanksMessage"));
      setFbMode(rating);
      setFbSent(true);
    } catch {
      Alert.alert(t("result.alertError"), t("result.feedbackError"));
    }
  }

  const whySpecialty = result.why_specialty_tr;

  return (
    <ScreenContainer>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <Card style={styles.cardSpacing}>
          <MutedText style={[styles.cardLabel, rtlText]}>{t("result.whereToGo")}</MutedText>
          <Text style={[styles.specialtyName, rtlText]}>{result.recommended_specialty.name_tr}</Text>
          <Badge style={styles.urgencyBadge} textStyle={styles.urgencyText}>
            {result.urgency === "ROUTINE"
              ? t("result.urgencyRoutine")
              : result.urgency === "SAME_DAY"
                ? t("result.urgencySameDay")
                : t("result.urgencyAcil")}
          </Badge>
        </Card>

        <View style={styles.sectionSpacing}>
          <ConfidenceBar value={confidence} label={label} hint={hint} />
        </View>

        {Array.isArray(whySpecialty) && whySpecialty.length > 0 ? (
          <Card style={styles.cardSpacing}>
            <SectionTitle style={rtlText}>{t("result.whySpecialty")}</SectionTitle>
            {whySpecialty.map((line, i) => (
              <Text key={i} style={[styles.bulletText, rtlText]}>
                • {line}
              </Text>
            ))}
          </Card>
        ) : null}

        <Card style={styles.cardSpacing}>
          <SectionTitle style={rtlText}>{t("result.possibleConditions")}</SectionTitle>
          {result.top_conditions.map((c, i) => (
            <View key={i} style={styles.conditionRow}>
              <Text style={[styles.conditionLabel, rtlText]}>{c.disease_label}</Text>
              <Text style={[styles.conditionScore, rtlText]}>%{Math.round(c.score_0_1 * 100)}</Text>
            </View>
          ))}
        </Card>

        <Card style={styles.cardSpacing}>
          <View style={styles.summaryHeader}>
            <SectionTitle style={[styles.summaryTitle, rtlText]}>{t("result.summaryForDoctor")}</SectionTitle>
            <View style={styles.shareRow}>
              <SecondaryButton onPress={onShareSummary} style={styles.copyButton} textStyle={styles.copyButtonText}>
                {t("result.shareAsText")}
              </SecondaryButton>
              <SecondaryButton onPress={onSharePdf} disabled={sharingPdf} style={styles.copyButton} textStyle={styles.copyButtonText}>
                {sharingPdf ? "…" : t("result.pdf")}
              </SecondaryButton>
              <SecondaryButton onPress={onDownloadText} disabled={downloadingText} style={styles.copyButton} textStyle={styles.copyButtonText}>
                {downloadingText ? "…" : t("result.downloadText")}
              </SecondaryButton>
            </View>
          </View>
          {result.doctor_ready_summary_tr.map((line, i) => (
            <Text key={i} style={[styles.bulletText, rtlText]}>
              • {line}
            </Text>
          ))}
        </Card>

        <Card style={styles.cardSpacing}>
          <SectionTitle style={rtlText}>{t("result.sendSummaryEmail")}</SectionTitle>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder={t("result.emailPlaceholder")}
            placeholderTextColor={tokens.colors.textMuted}
            style={[styles.emailInput, rtlText]}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            editable={!emailSent && !sendingEmail}
          />
          <PrimaryButton
            onPress={onSendEmail}
            disabled={!sessionId || !email.trim() || sendingEmail || emailSent}
            style={styles.sendEmailButton}
          >
            {sendingEmail ? t("common.loading") : emailSent ? t("result.emailSent") : t("result.sendEmail")}
          </PrimaryButton>
        </Card>

        <Card style={styles.cardSpacing}>
          <SectionTitle style={rtlText}>{t("result.warnings")}</SectionTitle>
          {result.safety_notes_tr.map((note, i) => (
            <Text key={i} style={[styles.safetyNote, rtlText]}>
              {note}
            </Text>
          ))}
        </Card>

        <Card style={styles.cardSpacing}>
          <SectionTitle style={rtlText}>{t("result.feedbackQuestion")}</SectionTitle>

          <View style={styles.feedbackRow}>
            <Pressable
              onPress={() => submitFeedback("up")}
              style={[
                styles.feedbackBtn,
                fbMode === "up" && styles.feedbackBtnActive,
              ]}
              disabled={fbSent}
              accessibilityRole="button"
              accessibilityLabel={t("common.yes")}
              accessibilityState={{ disabled: fbSent }}
            >
              <Text
                style={[
                  styles.feedbackBtnText,
                  fbMode === "up" && styles.feedbackBtnTextActive,
                  rtlText,
                ]}
              >
                {t("common.yes")}
              </Text>
            </Pressable>

            <Pressable
              onPress={() => {
                if (fbSent) return;
                setFbMode("down");
              }}
              style={[
                styles.feedbackBtn,
                fbMode === "down" && styles.feedbackBtnActive,
              ]}
              disabled={fbSent}
              accessibilityRole="button"
              accessibilityLabel={t("common.no")}
              accessibilityState={{ disabled: fbSent }}
            >
              <Text
                style={[
                  styles.feedbackBtnText,
                  fbMode === "down" && styles.feedbackBtnTextActive,
                  rtlText,
                ]}
              >
                {t("common.no")}
              </Text>
            </Pressable>
          </View>

          {fbMode === "down" && !fbSent ? (
            <View style={styles.feedbackCommentBox}>
              <Text style={[styles.feedbackHint, rtlText]}>{t("result.feedbackCommentHint")}</Text>
              <TextInput
                value={comment}
                onChangeText={setComment}
                placeholder={t("result.feedbackCommentPlaceholder")}
                placeholderTextColor={tokens.colors.textMuted}
                style={[styles.feedbackInput, rtlText]}
                multiline
                textAlignVertical="top"
              />
              <PrimaryButton
                onPress={() => submitFeedback("down")}
                style={styles.feedbackSubmitButton}
              >
                {t("result.feedbackSubmit")}
              </PrimaryButton>
            </View>
          ) : null}

          {fbSent ? (
            <Text style={[styles.feedbackThanks, rtlText]}>{t("result.feedbackThanksInline")}</Text>
          ) : null}
        </Card>

        <PrimaryButton
          onPress={() => {
            unregisterPushTokenIfNeeded();
            resetSession();
          }}
          style={styles.resetBtn}
          accessibilityRole="button"
          accessibilityLabel={t("common.newAssessment")}
        >
          {t("common.newAssessment")}
        </PrimaryButton>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    paddingVertical: tokens.spacing.lg,
    paddingBottom: tokens.spacing.xxl,
  },
  cardSpacing: {
    marginBottom: tokens.spacing.md,
  },
  sectionSpacing: {
    marginBottom: tokens.spacing.md,
  },
  cardLabel: {
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: tokens.spacing.xs,
  },
  specialtyName: {
    ...tokens.typography.title,
    marginBottom: tokens.spacing.sm,
  },
  urgencyBadge: {
    backgroundColor: "#E8EEF8",
    borderColor: "#D7E2F3",
  },
  urgencyText: {
    color: tokens.colors.textSecondary,
  },
  bulletText: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    marginBottom: tokens.spacing.xs,
  },
  conditionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
    paddingVertical: tokens.spacing.sm,
  },
  conditionLabel: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    flex: 1,
    marginRight: tokens.spacing.sm,
  },
  conditionScore: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    fontWeight: "700",
  },
  summaryHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: tokens.spacing.sm,
    gap: tokens.spacing.sm,
  },
  summaryTitle: {
    flex: 1,
    marginBottom: 0,
  },
  shareRow: {
    flexDirection: "row",
    gap: tokens.spacing.xs,
  },
  copyButton: {
    minHeight: 36,
    paddingVertical: tokens.spacing.xs,
    paddingHorizontal: tokens.spacing.sm,
  },
  copyButtonText: {
    fontSize: 13,
    lineHeight: 18,
  },
  emailInput: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    borderRadius: tokens.radius.md,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    minHeight: inputHeights.md,
    marginBottom: tokens.spacing.sm,
  },
  sendEmailButton: {
    marginTop: tokens.spacing.xs,
  },
  safetyNote: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
    marginBottom: tokens.spacing.xs,
    fontStyle: "italic",
  },
  feedbackRow: {
    flexDirection: "row",
    gap: tokens.spacing.sm,
  },
  feedbackBtn: {
    flex: 1,
    minHeight: inputHeights.md,
    borderRadius: tokens.radius.md,
    backgroundColor: tokens.colors.surfaceAlt,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
  },
  feedbackBtnActive: {
    backgroundColor: tokens.colors.primary,
    borderColor: tokens.colors.primary,
  },
  feedbackBtnText: {
    ...tokens.typography.button,
    color: tokens.colors.textPrimary,
  },
  feedbackBtnTextActive: {
    color: "#FFFFFF",
  },
  feedbackCommentBox: {
    marginTop: tokens.spacing.md,
    gap: tokens.spacing.sm,
  },
  feedbackHint: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
  },
  feedbackInput: {
    minHeight: 88,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    borderRadius: tokens.radius.md,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    backgroundColor: tokens.colors.surface,
    color: tokens.colors.textPrimary,
    ...tokens.typography.body,
  },
  feedbackSubmitButton: {
    backgroundColor: tokens.colors.error,
    borderColor: tokens.colors.error,
  },
  feedbackThanks: {
    marginTop: tokens.spacing.sm,
    ...tokens.typography.bodySmall,
    color: tokens.colors.success,
    fontWeight: "600",
  },
  resetBtn: {
    marginTop: tokens.spacing.xs,
    marginBottom: tokens.spacing.md,
  },
});
