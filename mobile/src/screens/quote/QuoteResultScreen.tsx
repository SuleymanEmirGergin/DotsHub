/**
 * Step 3 — render the QUOTE envelope.
 *
 * Shows the procedure summary, ranked clinics, fit-to-travel warnings
 * (if severity=warn), and CTAs to either fetch an itinerary or skip
 * to the lead form for a chosen clinic.
 */
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useQuoteStore } from "@/src/state/quoteStore";
import type { ClinicQuoteItem, FitToTravelWarning } from "@/src/state/htTypes";
import { tokens } from "@/src/ui/designTokens";
import {
  Badge,
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
} from "@/src/ui/primitives";

export default function QuoteResultScreen() {
  const { t, isRTL } = useI18n();
  const quote = useQuoteStore((s) => s.quote);
  const selected = useQuoteStore((s) => s.selectedClinic);
  const pickClinic = useQuoteStore((s) => s.pickClinic);
  const setStep = useQuoteStore((s) => s.setStep);

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  if (!quote) {
    return (
      <ScreenContainer>
        <MutedText style={[rtlText, { textAlign: "center", marginTop: 40 }]}>
          {t("common.loading")}
        </MutedText>
      </ScreenContainer>
    );
  }

  const warnings = (quote.fit_to_travel_warnings || []).filter(
    (w) => w.severity === "warn",
  );

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable
          onPress={() => setStep("profile")}
          style={styles.backLink}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Text style={[styles.backText, rtlText]}>← {t("common.back")}</Text>
        </Pressable>

        <Text style={[styles.title, rtlText]}>{t("quote.result.title")}</Text>
        <Text style={[styles.procedureName, rtlText]}>
          {quote.procedure.name_tr}
        </Text>
        {quote.procedure.duration_days ? (
          <MutedText style={[styles.procedureMeta, rtlText]}>
            {t("quote.browse.stayDays")}:{" "}
            {quote.procedure.duration_days.min_stay}–
            {quote.procedure.duration_days.max_stay} •{" "}
            {t("quote.browse.recoveryDays")}:{" "}
            {quote.procedure.duration_days.recovery_total}
          </MutedText>
        ) : null}

        {warnings.length > 0 ? (
          <WarningsCard warnings={warnings} title={t("quote.result.warnings")} rtl={Boolean(rtlText)} />
        ) : null}

        {quote.summary_tr ? (
          <Card style={styles.summaryCard}>
            <Text style={[styles.summaryLabel, rtlText]}>
              {t("quote.result.summaryLabel")}
            </Text>
            <Text style={[styles.summaryText, rtlText]}>{quote.summary_tr}</Text>
          </Card>
        ) : null}

        <Text style={[styles.sectionTitle, rtlText]}>
          {t("quote.result.clinicsTitle")}
        </Text>

        {quote.clinics.map((c) => (
          <ClinicCard
            key={c.clinic_id}
            clinic={c}
            selected={selected?.clinic_id === c.clinic_id}
            onPress={() => pickClinic(c)}
            t={t}
            rtl={Boolean(rtlText)}
          />
        ))}

        <View style={styles.actions}>
          <SecondaryButton
            onPress={() => setStep("itinerary")}
            disabled={!selected}
            accessibilityLabel={t("quote.result.viewItinerary")}
          >
            {t("quote.result.viewItinerary")}
          </SecondaryButton>
          <PrimaryButton
            onPress={() => setStep("lead")}
            disabled={!selected}
            accessibilityLabel={t("quote.result.acceptCta")}
            style={styles.cta}
          >
            {t("quote.result.acceptCta")}
          </PrimaryButton>
        </View>
      </ScrollView>
    </ScreenContainer>
  );
}

function ClinicCard({
  clinic,
  selected,
  onPress,
  t,
  rtl,
}: {
  clinic: ClinicQuoteItem;
  selected: boolean;
  onPress: () => void;
  t: (key: string) => string;
  rtl: boolean;
}) {
  const rtlText = rtl ? RTL_TEXT_STYLE : undefined;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${clinic.clinic_name}, €${clinic.price_eur}`}
      accessibilityState={{ selected }}
      style={({ pressed }) => [pressed && { opacity: 0.85 }]}
    >
      <Card style={[styles.clinicCard, selected && styles.clinicCardSelected]}>
        <View style={styles.clinicHeader}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.clinicName, rtlText]}>{clinic.clinic_name}</Text>
            <MutedText style={[styles.clinicCity, rtlText]}>
              {clinic.city}
            </MutedText>
          </View>
          <View style={styles.priceBlock}>
            <Text style={[styles.priceText, rtlText]}>€{clinic.price_eur}</Text>
            <MutedText style={[styles.priceCurrency, rtlText]}>EUR</MutedText>
          </View>
        </View>

        <View style={styles.metaRow}>
          <Badge>★ {clinic.average_rating_5.toFixed(1)}</Badge>
          <Badge>
            {t("quote.result.responseHours").replace(
              "{hours}",
              String(clinic.consult_response_hours),
            )}
          </Badge>
          {clinic.certifications.slice(0, 2).map((c) => (
            <Badge key={c}>{c}</Badge>
          ))}
        </View>

        {clinic.why_recommended_tr && clinic.why_recommended_tr.length > 0 ? (
          <View style={styles.whyBlock}>
            <Text style={[styles.whyTitle, rtlText]}>
              {t("quote.result.whyRecommended")}
            </Text>
            {clinic.why_recommended_tr.map((line, i) => (
              <Text key={i} style={[styles.whyLine, rtlText]}>
                • {line}
              </Text>
            ))}
          </View>
        ) : null}

        {clinic.package_features && clinic.package_features.length > 0 ? (
          <View style={styles.featuresBlock}>
            <Text style={[styles.featuresTitle, rtlText]}>
              {t("quote.result.packageFeatures")}
            </Text>
            <Text style={[styles.featuresText, rtlText]}>
              {clinic.package_features.join(" • ")}
            </Text>
          </View>
        ) : null}
      </Card>
    </Pressable>
  );
}

function WarningsCard({
  warnings,
  title,
  rtl,
}: {
  warnings: FitToTravelWarning[];
  title: string;
  rtl: boolean;
}) {
  const rtlText = rtl ? RTL_TEXT_STYLE : undefined;
  return (
    <Card style={styles.warningsCard}>
      <Text style={[styles.warningsTitle, rtlText]}>⚠ {title}</Text>
      {warnings.map((w) => (
        <View key={w.rule_id} style={styles.warningItem}>
          <Text style={[styles.warningReason, rtlText]}>{w.reason_tr}</Text>
          <MutedText style={[styles.warningRecommendation, rtlText]}>
            {w.recommendation_tr}
          </MutedText>
        </View>
      ))}
    </Card>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: tokens.spacing.lg },
  scroll: { paddingBottom: tokens.spacing.xxl },
  backLink: {
    paddingVertical: tokens.spacing.xs,
    marginBottom: tokens.spacing.sm,
  },
  backText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
  },
  title: {
    ...tokens.typography.title,
    marginBottom: tokens.spacing.xs,
  },
  procedureName: {
    ...tokens.typography.h1,
    marginBottom: 2,
  },
  procedureMeta: {
    marginBottom: tokens.spacing.md,
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
  warningItem: { marginTop: tokens.spacing.sm },
  warningReason: {
    ...tokens.typography.bodySmall,
    color: "#5A3A00",
    marginBottom: 2,
  },
  warningRecommendation: { color: "#7A4F00" },
  summaryCard: { marginBottom: tokens.spacing.md },
  summaryLabel: {
    ...tokens.typography.h2,
    marginBottom: tokens.spacing.xs,
  },
  summaryText: { ...tokens.typography.body },
  sectionTitle: {
    ...tokens.typography.h1,
    marginVertical: tokens.spacing.md,
  },
  clinicCard: {
    marginBottom: tokens.spacing.md,
    borderWidth: 1,
    borderColor: tokens.colors.border,
  },
  clinicCardSelected: {
    borderColor: tokens.colors.primary,
    borderWidth: 2,
  },
  clinicHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  clinicName: {
    ...tokens.typography.h2,
  },
  clinicCity: {
    marginTop: 2,
  },
  priceBlock: {
    alignItems: "flex-end",
    marginLeft: tokens.spacing.md,
  },
  priceText: {
    ...tokens.typography.h1,
    color: tokens.colors.textPrimary,
  },
  priceCurrency: {},
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: tokens.spacing.xs,
    marginTop: tokens.spacing.sm,
  },
  whyBlock: {
    marginTop: tokens.spacing.md,
    paddingTop: tokens.spacing.md,
    borderTopWidth: 1,
    borderTopColor: tokens.colors.border,
  },
  whyTitle: {
    ...tokens.typography.h2,
    fontSize: 14,
    marginBottom: tokens.spacing.xs,
  },
  whyLine: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
    marginVertical: 2,
  },
  featuresBlock: {
    marginTop: tokens.spacing.sm,
  },
  featuresTitle: {
    ...tokens.typography.bodySmall,
    fontWeight: "600",
    marginBottom: 2,
  },
  featuresText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
  },
  actions: {
    flexDirection: "row",
    gap: tokens.spacing.md,
    marginTop: tokens.spacing.lg,
  },
  cta: { flex: 1 },
});
