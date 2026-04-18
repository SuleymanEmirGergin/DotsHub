import React, { useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import type { TopCondition } from "@/src/state/types";
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
import { buildSummaryHtml, shareSummaryAsPdf } from "@/utils/sharePdf";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";

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
      await Share.share({
        message: text,
        title: t("summary.title"),
      });
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
          <Text style={[styles.possibleConditionsSubtitle, rtlText]}>
            {t("result.possibleConditionsSubtitle")}
          </Text>
          {result.top_conditions.map((c, i) => (
            <ConditionItem
              key={i}
              condition={c}
              rtlText={rtlText}
              labels={{
                curated: t("result.condCuratedBadge"),
                icd10: t("result.condIcd10"),
                description: t("result.condDescription"),
                doctorQuestions: t("result.condDoctorQuestions"),
                symptomsToTrack: t("result.condSymptomsToTrack"),
                whenToEscalate: t("result.condWhenToEscalate"),
                selfCare: t("result.condSelfCare"),
                urgencyNote: t("result.condUrgencyNote"),
                expandHint: t("result.condExpandHint"),
                collapseHint: t("result.condCollapseHint"),
              }}
            />
          ))}
          {result.top_conditions.some((c) => c.disclaimer_tr) && (
            <Text style={[styles.possibleConditionsDisclaimer, rtlText]}>
              {result.top_conditions.find((c) => c.disclaimer_tr)?.disclaimer_tr}
            </Text>
          )}
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
          onPress={resetSession}
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
  possibleConditionsSubtitle: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    marginTop: -tokens.spacing.xs,
    marginBottom: tokens.spacing.sm,
  },
  possibleConditionsDisclaimer: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    marginTop: tokens.spacing.sm,
    fontStyle: "italic",
  },
  conditionItemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: tokens.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
  },
  conditionItemLabelRow: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: tokens.spacing.xs,
    marginRight: tokens.spacing.sm,
  },
  conditionCuratedBadge: {
    ...tokens.typography.caption,
    color: "#2F4F8F",
    backgroundColor: "#E8EEF8",
    borderColor: "#D7E2F3",
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 1,
    fontSize: 10,
  },
  conditionExpandBody: {
    paddingVertical: tokens.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
  },
  conditionSectionLabel: {
    ...tokens.typography.caption,
    color: tokens.colors.textPrimary,
    fontWeight: "700",
    marginTop: tokens.spacing.sm,
    marginBottom: tokens.spacing.xs / 2,
  },
  conditionIcd10Text: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    fontFamily: "monospace",
    marginBottom: tokens.spacing.xs,
  },
  conditionDescText: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    marginBottom: tokens.spacing.xs,
  },
  conditionExpandHint: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    marginRight: tokens.spacing.xs,
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


// ────────────────────────────────────────────────────────────────────────
// ConditionItem — expandable row for a top_conditions entry.
//
// Opsiyon A (pre-triage product decision): low-key "Olası durumlar" list
// below the specialty card. Tapping a row expands curated prep fields
// (ICD-10, doctor questions, symptoms to track, escalation triggers,
// self-care). Kaggle-candidate entries only carry a short description
// when one exists, so their expand state is near-empty but the tap
// target is still present for consistency.
// ────────────────────────────────────────────────────────────────────────

type ConditionItemLabels = {
  curated: string;
  icd10: string;
  description: string;
  doctorQuestions: string;
  symptomsToTrack: string;
  whenToEscalate: string;
  selfCare: string;
  urgencyNote: string;
  expandHint: string;
  collapseHint: string;
};

function ConditionItem({
  condition,
  rtlText,
  labels,
}: {
  condition: TopCondition;
  rtlText: any;
  labels: ConditionItemLabels;
}) {
  const [expanded, setExpanded] = useState(false);
  const curated = condition.source_type === "curated";
  const hasExpandable =
    !!condition.disease_description_tr ||
    !!condition.disease_description ||
    !!condition.icd10 ||
    (condition.doktora_sorulacak_sorular_tr?.length ?? 0) > 0 ||
    (condition.izlenecek_belirtiler_tr?.length ?? 0) > 0 ||
    (condition.ne_zaman_tekrar_basvur_tr?.length ?? 0) > 0 ||
    (condition.self_care_tr?.length ?? 0) > 0 ||
    !!condition.aciliyet_notu_tr;

  return (
    <View>
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityLabel={condition.disease_label}
        accessibilityHint={expanded ? labels.collapseHint : labels.expandHint}
        onPress={() => hasExpandable && setExpanded((v) => !v)}
        activeOpacity={hasExpandable ? 0.6 : 1}
        style={styles.conditionItemHeader}
      >
        <View style={styles.conditionItemLabelRow}>
          <Text style={[styles.conditionLabel, rtlText]}>
            {condition.disease_label}
          </Text>
          {curated ? (
            <Text style={[styles.conditionCuratedBadge, rtlText]}>
              {labels.curated}
            </Text>
          ) : null}
        </View>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          {hasExpandable ? (
            <Text style={[styles.conditionExpandHint, rtlText]}>
              {expanded ? "▲" : "▼"}
            </Text>
          ) : null}
          <Text style={[styles.conditionScore, rtlText]}>
            %{Math.round(condition.score_0_1 * 100)}
          </Text>
        </View>
      </TouchableOpacity>

      {expanded && hasExpandable ? (
        <View style={styles.conditionExpandBody}>
          {condition.icd10 ? (
            <Text style={[styles.conditionIcd10Text, rtlText]}>
              {labels.icd10}: {condition.icd10}
            </Text>
          ) : null}
          {condition.disease_description_tr ||
          condition.disease_description ? (
            <>
              <Text style={[styles.conditionSectionLabel, rtlText]}>
                {labels.description}
              </Text>
              <Text style={[styles.conditionDescText, rtlText]}>
                {condition.disease_description_tr ??
                  condition.disease_description}
              </Text>
            </>
          ) : null}
          {condition.doktora_sorulacak_sorular_tr?.length ? (
            <>
              <Text style={[styles.conditionSectionLabel, rtlText]}>
                {labels.doctorQuestions}
              </Text>
              {condition.doktora_sorulacak_sorular_tr.map((q, i) => (
                <Text key={i} style={[styles.bulletText, rtlText]}>
                  • {q}
                </Text>
              ))}
            </>
          ) : null}
          {condition.izlenecek_belirtiler_tr?.length ? (
            <>
              <Text style={[styles.conditionSectionLabel, rtlText]}>
                {labels.symptomsToTrack}
              </Text>
              {condition.izlenecek_belirtiler_tr.map((s, i) => (
                <Text key={i} style={[styles.bulletText, rtlText]}>
                  • {s}
                </Text>
              ))}
            </>
          ) : null}
          {condition.ne_zaman_tekrar_basvur_tr?.length ? (
            <>
              <Text style={[styles.conditionSectionLabel, rtlText]}>
                {labels.whenToEscalate}
              </Text>
              {condition.ne_zaman_tekrar_basvur_tr.map((e, i) => (
                <Text key={i} style={[styles.bulletText, rtlText]}>
                  • {e}
                </Text>
              ))}
            </>
          ) : null}
          {condition.self_care_tr?.length ? (
            <>
              <Text style={[styles.conditionSectionLabel, rtlText]}>
                {labels.selfCare}
              </Text>
              {condition.self_care_tr.map((s, i) => (
                <Text key={i} style={[styles.bulletText, rtlText]}>
                  • {s}
                </Text>
              ))}
            </>
          ) : null}
          {condition.aciliyet_notu_tr ? (
            <>
              <Text style={[styles.conditionSectionLabel, rtlText]}>
                {labels.urgencyNote}
              </Text>
              <Text style={[styles.conditionDescText, rtlText]}>
                {condition.aciliyet_notu_tr}
              </Text>
            </>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
