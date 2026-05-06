import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  getSessionDetail,
  SessionDetailError,
  type SessionDetail,
} from "@/src/api/sessionsClient";
import { tokens, screenPadding } from "@/src/ui/designTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
} from "@/src/ui/primitives";
import { useI18n } from "@/i18n/I18nProvider";

/**
 * Read-only detail of one past triage session, opened from
 * HistoryScreen. Mirrors the ResultScreen layout — specialty header,
 * conditions, doctor-ready summary, emergency reason on red rows —
 * but stripped of the post-result CTAs (PDF export, "Yeni
 * Değerlendirme") that don't apply to a historical record.
 *
 * Auth: the underlying GET enforces device ownership server-side
 * (404 on wrong device, anti-IDOR). The screen renders the same
 * "not found" copy for that case so a session id leaked elsewhere
 * doesn't reveal whether it exists.
 */

type Props = {
  sessionId: string;
  onBack: () => void;
};

export default function SessionDetailScreen({ sessionId, onBack }: Props) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCopy, setErrorCopy] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorCopy(null);
    setNotFound(false);
    getSessionDetail(sessionId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof SessionDetailError && err.status === 404) {
          setNotFound(true);
        } else if (err instanceof SessionDetailError && err.message_tr) {
          setErrorCopy(err.message_tr);
        } else {
          setErrorCopy(t("sessionDetail.errorLoading"));
        }
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, t]);

  const isEmergency = detail?.envelope_type === "EMERGENCY";

  return (
    <ScreenContainer style={styles.container}>
      <View style={styles.header}>
        <Pressable
          onPress={onBack}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel={t("sessionDetail.back")}
        >
          <Text style={styles.backText}>{t("sessionDetail.back")}</Text>
        </Pressable>
        <Text style={styles.title}>{t("sessionDetail.title")}</Text>
        <View style={styles.backBtn} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={tokens.colors.primary} />
          <MutedText style={styles.centerText}>
            {t("sessionDetail.loading")}
          </MutedText>
        </View>
      ) : notFound ? (
        <View style={styles.center}>
          <Text style={styles.errorTitle}>
            {t("sessionDetail.notFoundTitle")}
          </Text>
          <MutedText style={styles.centerText}>
            {t("sessionDetail.notFoundBody")}
          </MutedText>
          <SecondaryButton onPress={onBack} style={styles.errorBtn}>
            {t("sessionDetail.back")}
          </SecondaryButton>
        </View>
      ) : errorCopy ? (
        <View style={styles.center}>
          <Text style={styles.errorTitle}>
            {t("sessionDetail.errorTitle")}
          </Text>
          <MutedText style={styles.centerText}>{errorCopy}</MutedText>
          <SecondaryButton onPress={onBack} style={styles.errorBtn}>
            {t("sessionDetail.back")}
          </SecondaryButton>
        </View>
      ) : detail ? (
        <ScrollView contentContainerStyle={styles.scroll}>
          {isEmergency ? <EmergencyHeader detail={detail} /> : null}

          <Card style={styles.specialtyCard}>
            <View style={styles.specialtyHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.specialtyLabel}>
                  {t("sessionDetail.recommendedSpecialty")}
                </Text>
                <Text style={styles.specialtyName}>
                  {detail.recommended_specialty_tr ||
                    t("sessionDetail.unknownSpecialty")}
                </Text>
              </View>
              {typeof detail.confidence_0_1 === "number" ? (
                <View style={styles.confidenceChip}>
                  <Text style={styles.confidenceChipText}>
                    %{Math.round((detail.confidence_0_1 ?? 0) * 100)}{" "}
                    {t("sessionDetail.confidence")}
                  </Text>
                </View>
              ) : null}
            </View>
            {detail.confidence_explain_tr ? (
              <Text style={styles.specialtyExplain}>
                {detail.confidence_explain_tr}
              </Text>
            ) : null}
            <MutedText style={styles.dateLine}>
              {formatDateTr(detail.created_at)} ·{" "}
              {t("sessionDetail.questionCount").replace(
                "{{count}}",
                String(detail.turn_index),
              )}
            </MutedText>
          </Card>

          {detail.top_conditions.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                {t("sessionDetail.possibleConditions").replace(
                  "{{count}}",
                  String(detail.top_conditions.length),
                )}
              </Text>
              <Card>
                {detail.top_conditions.map((c, i) => (
                  <View
                    key={`${c.disease_label}-${i}`}
                    style={[
                      styles.conditionRow,
                      i > 0 && styles.conditionRowBorder,
                    ]}
                  >
                    <Text style={styles.conditionLabel}>
                      {String(c.disease_label ?? "—")}
                    </Text>
                    {typeof c.score_0_1 === "number" ? (
                      <View style={styles.scoreChip}>
                        <Text style={styles.scoreChipText}>
                          %{Math.round((c.score_0_1 ?? 0) * 100)}
                        </Text>
                      </View>
                    ) : null}
                  </View>
                ))}
              </Card>
            </View>
          ) : null}

          {detail.why_specialty_tr.length > 0 ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                {t("sessionDetail.whySpecialty")}
              </Text>
              <Card>
                {detail.why_specialty_tr.map((line, i) => (
                  <Text
                    key={i}
                    style={[
                      styles.bulletLine,
                      i > 0 && styles.bulletLineSpacing,
                    ]}
                  >
                    • {line}
                  </Text>
                ))}
              </Card>
            </View>
          ) : null}

          {detail.input_text ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                {t("sessionDetail.originalSymptom")}
              </Text>
              <Card>
                <Text style={styles.inputTextLine}>{detail.input_text}</Text>
              </Card>
            </View>
          ) : null}
        </ScrollView>
      ) : null}
    </ScreenContainer>
  );
}

/** Red banner + 112'yi Ara button for sessions that ended in EMERGENCY. */
function EmergencyHeader({ detail }: { detail: SessionDetail }) {
  const { t } = useI18n();
  return (
    <View style={styles.emergencyHeader}>
      <View style={styles.emergencyHeaderRow}>
        <Text style={styles.emergencyTitle}>{t("sessionDetail.emergencyTitle")}</Text>
      </View>
      {detail.emergency_reason_tr ? (
        <Text style={styles.emergencyReason}>{detail.emergency_reason_tr}</Text>
      ) : null}
      <PrimaryButton
        onPress={() => Linking.openURL("tel:112")}
        style={styles.emergencyCallBtn}
        textStyle={styles.emergencyCallBtnText}
        accessibilityLabel={t("sessionDetail.call112")}
      >
        📞 {t("sessionDetail.call112")}
      </PrimaryButton>
    </View>
  );
}

// "28 Nisan 2026, 14:32" — keeps local-format-string allocation out of
// hot paths but small enough to inline.
const _TR_MONTHS = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];
function formatDateTr(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = d.getDate();
  const month = _TR_MONTHS[d.getMonth()];
  const year = d.getFullYear();
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  return `${day} ${month} ${year}, ${hh}:${mm}`;
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 0 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: screenPadding,
    paddingVertical: tokens.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
    backgroundColor: tokens.colors.surface,
  },
  backBtn: { width: 60 },
  backText: {
    ...tokens.typography.body,
    color: tokens.colors.primary,
    fontWeight: "600",
  },
  title: { ...tokens.typography.h2, textAlign: "center", flex: 1 },
  scroll: {
    padding: screenPadding,
    paddingBottom: tokens.spacing.xxl,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: screenPadding,
  },
  centerText: { textAlign: "center", marginTop: tokens.spacing.md },
  errorTitle: {
    ...tokens.typography.h1,
    marginBottom: tokens.spacing.sm,
    textAlign: "center",
  },
  errorBtn: { marginTop: tokens.spacing.lg },
  specialtyCard: { marginBottom: tokens.spacing.lg },
  specialtyHeaderRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: tokens.spacing.md,
  },
  specialtyLabel: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  specialtyName: {
    ...tokens.typography.title,
    marginTop: 2,
  },
  specialtyExplain: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    marginTop: tokens.spacing.sm,
  },
  dateLine: { marginTop: tokens.spacing.sm },
  confidenceChip: {
    backgroundColor: tokens.colors.infoBg,
    borderColor: tokens.colors.infoBorder,
    borderWidth: 1,
    borderRadius: tokens.radius.pill,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: 4,
  },
  confidenceChipText: {
    ...tokens.typography.caption,
    color: tokens.colors.infoText,
    fontWeight: "700",
  },
  section: { marginBottom: tokens.spacing.lg },
  sectionTitle: {
    ...tokens.typography.h2,
    marginBottom: tokens.spacing.sm,
  },
  conditionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: tokens.spacing.md,
  },
  conditionRowBorder: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: tokens.colors.border,
  },
  conditionLabel: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    fontWeight: "600",
    flex: 1,
  },
  scoreChip: {
    backgroundColor: tokens.colors.surfaceAlt,
    borderRadius: tokens.radius.sm,
    paddingHorizontal: tokens.spacing.sm,
    paddingVertical: 2,
  },
  scoreChipText: {
    ...tokens.typography.caption,
    fontWeight: "700",
    color: tokens.colors.textSecondary,
  },
  bulletLine: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
  },
  bulletLineSpacing: { marginTop: tokens.spacing.xs },
  inputTextLine: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    fontStyle: "italic",
  },
  emergencyHeader: {
    backgroundColor: tokens.colors.errorBg,
    borderLeftWidth: 4,
    borderLeftColor: tokens.colors.error,
    borderRadius: tokens.radius.lg,
    padding: tokens.spacing.lg,
    marginBottom: tokens.spacing.lg,
  },
  emergencyHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: tokens.spacing.sm,
  },
  emergencyTitle: {
    ...tokens.typography.h2,
    color: tokens.colors.error,
  },
  emergencyReason: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    marginBottom: tokens.spacing.md,
  },
  emergencyCallBtn: {
    backgroundColor: tokens.colors.error,
    borderColor: tokens.colors.error,
  },
  emergencyCallBtnText: { color: "#FFFFFF" },
});
