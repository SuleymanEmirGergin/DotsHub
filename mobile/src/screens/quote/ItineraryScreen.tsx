/**
 * Step 4 (optional) — render the ITINERARY envelope.
 *
 * The patient picked a clinic on the previous screen; here they enter
 * an arrival date and we fetch a day-by-day plan they can show to a
 * doctor or travel agent.
 */
import React, { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useQuoteStore } from "@/src/state/quoteStore";
import { tokens } from "@/src/ui/designTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
} from "@/src/ui/primitives";

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export default function ItineraryScreen() {
  const { t, isRTL } = useI18n();
  const itinerary = useQuoteStore((s) => s.itinerary);
  const fetchItinerary = useQuoteStore((s) => s.fetchItinerary);
  const setStep = useQuoteStore((s) => s.setStep);
  const loading = useQuoteStore((s) => s.loading);

  const [dateStr, setDateStr] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  const handleFetch = async () => {
    if (!ISO_DATE_RE.test(dateStr)) {
      setLocalError(t("quote.itinerary.dateError"));
      return;
    }
    setLocalError(null);
    await fetchItinerary(dateStr);
  };

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable
          onPress={() => setStep("quote")}
          style={styles.backLink}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Text style={[styles.backText, rtlText]}>← {t("common.back")}</Text>
        </Pressable>
        <Text style={[styles.title, rtlText]}>
          {t("quote.itinerary.title")}
        </Text>

        {!itinerary ? (
          <Card style={styles.card}>
            <Text style={[styles.fieldLabel, rtlText]}>
              {t("quote.itinerary.dateLabel")}
            </Text>
            <TextInput
              value={dateStr}
              onChangeText={setDateStr}
              placeholder="2026-05-15"
              autoCapitalize="none"
              keyboardType="default"
              style={styles.input}
              accessibilityLabel={t("quote.itinerary.dateLabel")}
              accessibilityHint={t("quote.itinerary.dateHint")}
            />
            <MutedText style={[styles.fieldHelp, rtlText]}>
              {t("quote.itinerary.dateHint")}
            </MutedText>
            {localError ? (
              <Text style={[styles.errorText, rtlText]}>{localError}</Text>
            ) : null}
            <PrimaryButton
              onPress={handleFetch}
              disabled={loading}
              style={styles.cta}
            >
              {loading ? t("common.loading") : t("quote.itinerary.fetchCta")}
            </PrimaryButton>
          </Card>
        ) : (
          <>
            <MutedText style={[styles.subtitle, rtlText]}>
              {t("quote.itinerary.summary")
                .replace("{procedure}", itinerary.procedure_name_tr)
                .replace("{clinic}", itinerary.clinic_name)
                .replace("{days}", String(itinerary.total_days))}
            </MutedText>

            {itinerary.fit_to_travel_warnings.length > 0 ? (
              <Card style={styles.warningsCard}>
                <Text style={[styles.warningsTitle, rtlText]}>
                  ⚠ {t("quote.result.warnings")}
                </Text>
                {itinerary.fit_to_travel_warnings.map((w) => (
                  <View key={w.rule_id} style={{ marginTop: tokens.spacing.xs }}>
                    <Text style={[styles.warningReason, rtlText]}>
                      {w.reason_tr}
                    </Text>
                    <MutedText style={rtlText}>{w.recommendation_tr}</MutedText>
                  </View>
                ))}
              </Card>
            ) : null}

            {itinerary.items.map((item) => (
              <Card key={`${item.day}-${item.date}`} style={styles.dayCard}>
                <Text style={[styles.dayBadge, rtlText]}>
                  {t("quote.itinerary.dayLabel").replace(
                    "{n}",
                    String(item.day),
                  )}{" "}
                  • {item.date}
                </Text>
                <Text style={[styles.dayTitle, rtlText]}>{item.title_tr}</Text>
                <MutedText style={[styles.dayDescription, rtlText]}>
                  {item.description_tr}
                </MutedText>
              </Card>
            ))}

            {itinerary.pre_op_requirements.length > 0 ? (
              <Card style={styles.preOpCard}>
                <Text style={[styles.fieldLabel, rtlText]}>
                  {t("quote.itinerary.preOpTitle")}
                </Text>
                {itinerary.pre_op_requirements.map((r) => (
                  <Text key={r} style={[styles.preOpItem, rtlText]}>
                    • {r}
                  </Text>
                ))}
              </Card>
            ) : null}

            <View style={styles.actions}>
              <SecondaryButton onPress={() => setStep("quote")}>
                {t("common.back")}
              </SecondaryButton>
              <PrimaryButton
                onPress={() => setStep("lead")}
                style={styles.cta}
                accessibilityLabel={t("quote.result.acceptCta")}
              >
                {t("quote.result.acceptCta")}
              </PrimaryButton>
            </View>
          </>
        )}
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: tokens.spacing.lg },
  scroll: { paddingBottom: tokens.spacing.xxl },
  backLink: { paddingVertical: tokens.spacing.xs, marginBottom: tokens.spacing.sm },
  backText: { ...tokens.typography.bodySmall, color: tokens.colors.textSecondary },
  title: { ...tokens.typography.title, marginBottom: tokens.spacing.sm },
  subtitle: { marginBottom: tokens.spacing.md },
  card: { marginBottom: tokens.spacing.md },
  fieldLabel: { ...tokens.typography.h2, marginBottom: tokens.spacing.xs },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    borderRadius: tokens.radius.md,
    backgroundColor: tokens.colors.surface,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    fontSize: 16,
    color: tokens.colors.textPrimary,
  },
  fieldHelp: { marginTop: tokens.spacing.xs, marginBottom: tokens.spacing.md },
  errorText: { color: tokens.colors.error, marginBottom: tokens.spacing.sm },
  cta: { flex: 1, marginTop: tokens.spacing.md },
  dayCard: { marginBottom: tokens.spacing.sm },
  dayBadge: {
    ...tokens.typography.caption,
    color: tokens.colors.primary,
    fontWeight: "700",
    marginBottom: 2,
  },
  dayTitle: { ...tokens.typography.h2, marginBottom: 2 },
  dayDescription: {},
  preOpCard: { marginTop: tokens.spacing.md },
  preOpItem: {
    ...tokens.typography.bodySmall,
    marginVertical: 2,
  },
  warningsCard: {
    backgroundColor: "#FFF7E6",
    borderColor: "#F6C879",
    marginBottom: tokens.spacing.md,
  },
  warningsTitle: {
    ...tokens.typography.h2,
    color: "#7A4F00",
    marginBottom: tokens.spacing.xs,
  },
  warningReason: { ...tokens.typography.bodySmall, color: "#5A3A00" },
  actions: {
    flexDirection: "row",
    gap: tokens.spacing.md,
    marginTop: tokens.spacing.md,
  },
});
