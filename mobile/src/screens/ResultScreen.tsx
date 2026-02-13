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
import { buildSummaryHtml, shareSummaryAsPdf } from "../../../utils/sharePdf";

export default function ResultScreen() {
  const result = useTriageStore((s) => s.result)!;
  const sessionId = useTriageStore((s) => s.sessionId);
  const resetSession = useTriageStore((s) => s.resetSession);

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
  const disclaimer = "Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır.";

  async function onShareSummary() {
    try {
      await Share.share({
        message: summaryText + "\n\n" + disclaimer,
        title: "Ön-Triyaj Sonuç Özeti",
      });
    } catch {
      Alert.alert("Hata", "Paylaşım açılamadı.");
    }
  }

  async function onSharePdf() {
    setSharingPdf(true);
    try {
      const html = buildSummaryHtml({
        title: "Ön-Triyaj Asistanı - Sonuç Özeti",
        specialty: result.recommended_specialty.name_tr,
        urgency:
          result.urgency === "ROUTINE"
            ? "Rutin"
            : result.urgency === "SAME_DAY"
              ? "Bugün İçinde"
              : "Acil",
        rationale: Array.isArray(result.why_specialty_tr) ? result.why_specialty_tr : undefined,
        candidates: result.top_conditions.map((c) => ({
          label: c.disease_label,
          probability: c.score_0_1,
        })),
        summaryLines: result.doctor_ready_summary_tr,
        disclaimer,
      });
      const ok = await shareSummaryAsPdf(html, onShareSummary);
      if (!ok) Alert.alert("Bilgi", "PDF paylaşımı bu cihazda desteklenmiyor; metin paylaşıldı.");
    } catch {
      Alert.alert("Hata", "PDF oluşturulamadı.");
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
      Alert.alert("Teşekkürler", "Geri bildirimin alındı.");
      setFbMode(rating);
      setFbSent(true);
    } catch {
      Alert.alert("Hata", "Geri bildirim gönderilemedi.");
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
          <MutedText style={styles.cardLabel}>Nereye gitmeliyim?</MutedText>
          <Text style={styles.specialtyName}>{result.recommended_specialty.name_tr}</Text>
          <Badge style={styles.urgencyBadge} textStyle={styles.urgencyText}>
            {result.urgency === "ROUTINE"
              ? "Rutin"
              : result.urgency === "SAME_DAY"
                ? "Bugün İçinde"
                : "Acil"}
          </Badge>
        </Card>

        <View style={styles.sectionSpacing}>
          <ConfidenceBar value={confidence} label={label} hint={hint} />
        </View>

        {Array.isArray(whySpecialty) && whySpecialty.length > 0 ? (
          <Card style={styles.cardSpacing}>
            <SectionTitle>Neden bu branş?</SectionTitle>
            {whySpecialty.map((line, i) => (
              <Text key={i} style={styles.bulletText}>
                • {line}
              </Text>
            ))}
          </Card>
        ) : null}

        <Card style={styles.cardSpacing}>
          <SectionTitle>Olası durumlar (tahmini)</SectionTitle>
          {result.top_conditions.map((c, i) => (
            <View key={i} style={styles.conditionRow}>
              <Text style={styles.conditionLabel}>{c.disease_label}</Text>
              <Text style={styles.conditionScore}>%{Math.round(c.score_0_1 * 100)}</Text>
            </View>
          ))}
        </Card>

        <Card style={styles.cardSpacing}>
          <View style={styles.summaryHeader}>
            <SectionTitle style={styles.summaryTitle}>Doktora gösterilecek özet</SectionTitle>
            <View style={styles.shareRow}>
              <SecondaryButton onPress={onShareSummary} style={styles.copyButton} textStyle={styles.copyButtonText}>
                Metin
              </SecondaryButton>
              <SecondaryButton onPress={onSharePdf} disabled={sharingPdf} style={styles.copyButton} textStyle={styles.copyButtonText}>
                {sharingPdf ? "…" : "PDF"}
              </SecondaryButton>
            </View>
          </View>
          {result.doctor_ready_summary_tr.map((line, i) => (
            <Text key={i} style={styles.bulletText}>
              • {line}
            </Text>
          ))}
        </Card>

        <Card style={styles.cardSpacing}>
          <SectionTitle>Uyarılar</SectionTitle>
          {result.safety_notes_tr.map((note, i) => (
            <Text key={i} style={styles.safetyNote}>
              {note}
            </Text>
          ))}
        </Card>

        <Card style={styles.cardSpacing}>
          <SectionTitle>Bu değerlendirme yardımcı oldu mu?</SectionTitle>

          <View style={styles.feedbackRow}>
            <Pressable
              onPress={() => submitFeedback("up")}
              style={[
                styles.feedbackBtn,
                fbMode === "up" && styles.feedbackBtnActive,
              ]}
              disabled={fbSent}
            >
              <Text
                style={[
                  styles.feedbackBtnText,
                  fbMode === "up" && styles.feedbackBtnTextActive,
                ]}
              >
                Evet
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
            >
              <Text
                style={[
                  styles.feedbackBtnText,
                  fbMode === "down" && styles.feedbackBtnTextActive,
                ]}
              >
                Hayır
              </Text>
            </Pressable>
          </View>

          {fbMode === "down" && !fbSent ? (
            <View style={styles.feedbackCommentBox}>
              <Text style={styles.feedbackHint}>Neyi eksik veya yanlış buldun? (opsiyonel)</Text>
              <TextInput
                value={comment}
                onChangeText={setComment}
                placeholder="Kısa not..."
                placeholderTextColor={tokens.colors.textMuted}
                style={styles.feedbackInput}
                multiline
                textAlignVertical="top"
              />
              <PrimaryButton
                onPress={() => submitFeedback("down")}
                style={styles.feedbackSubmitButton}
              >
                Gönder
              </PrimaryButton>
            </View>
          ) : null}

          {fbSent ? (
            <Text style={styles.feedbackThanks}>Geri bildirimin kaydedildi. Teşekkürler!</Text>
          ) : null}
        </Card>

        <PrimaryButton onPress={resetSession} style={styles.resetBtn}>
          Yeni Değerlendirme
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
