/**
 * Step 2 — patient profile (fit-to-travel screening inputs).
 *
 * Backend's HealthTourismProfile has ~22 boolean flags. We don't ask
 * about all of them on the form — just the ones relevant to elective
 * surgery as a class (smoking, anticoagulants, recent MI, pregnancy,
 * BMI). The rest stay false. Procedure-specific flags
 * (active_eye_infection for LASIK, etc.) are screened during the
 * in-person consultation, not on this form.
 *
 * Submitting fires `submitProfileForQuote` which posts to /v1/quote;
 * the response routes to quote / not_fit / error.
 */
import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useQuoteStore } from "@/src/state/quoteStore";
import type { HealthTourismProfile } from "@/src/state/htTypes";
import { tokens } from "@/src/ui/designTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
} from "@/src/ui/primitives";

const TOGGLE_FLAGS: Array<{ key: keyof HealthTourismProfile; labelKey: string }> = [
  { key: "smoker_active", labelKey: "quote.profile.smoker" },
  { key: "anticoagulant_therapy", labelKey: "quote.profile.anticoagulant" },
  { key: "recent_mi", labelKey: "quote.profile.recentMi" },
  { key: "uncontrolled_diabetes", labelKey: "quote.profile.uncontrolledDiabetes" },
  { key: "uncontrolled_hypertension", labelKey: "quote.profile.uncontrolledHypertension" },
  { key: "pregnancy", labelKey: "quote.profile.pregnancy" },
  { key: "active_cancer", labelKey: "quote.profile.activeCancer" },
  { key: "active_infection", labelKey: "quote.profile.activeInfection" },
];

export default function PatientProfileScreen() {
  const { t, isRTL } = useI18n();
  const profile = useQuoteStore((s) => s.profile);
  const procedure = useQuoteStore((s) => s.procedure);
  const patchProfile = useQuoteStore((s) => s.patchProfile);
  const submitProfileForQuote = useQuoteStore((s) => s.submitProfileForQuote);
  const setStep = useQuoteStore((s) => s.setStep);
  const loading = useQuoteStore((s) => s.loading);

  const [ageStr, setAgeStr] = useState(
    profile.age != null ? String(profile.age) : "",
  );
  const [bmiStr, setBmiStr] = useState(
    profile.bmi != null ? String(profile.bmi) : "",
  );

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  const handleSubmit = async () => {
    const age = parseInt(ageStr, 10);
    const bmi = parseFloat(bmiStr);
    patchProfile({
      age: Number.isFinite(age) ? age : null,
      bmi: Number.isFinite(bmi) ? bmi : null,
      bmi_over_35: Number.isFinite(bmi) && bmi >= 35,
      bmi_over_55: Number.isFinite(bmi) && bmi >= 55,
    });
    await submitProfileForQuote();
  };

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable
          onPress={() => setStep("browse")}
          style={styles.backLink}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Text style={[styles.backText, rtlText]}>← {t("common.back")}</Text>
        </Pressable>
        <Text style={[styles.title, rtlText]}>
          {t("quote.profile.title")}
        </Text>
        <MutedText style={[styles.subtitle, rtlText]}>
          {procedure
            ? t("quote.profile.procedureLabel")
                .replace("{procedure}", procedure.name.tr)
            : t("quote.profile.subtitle")}
        </MutedText>

        <Card style={styles.card}>
          <Text style={[styles.fieldLabel, rtlText]}>
            {t("quote.profile.ageLabel")}
          </Text>
          <TextInput
            value={ageStr}
            onChangeText={setAgeStr}
            keyboardType="numeric"
            placeholder={t("quote.profile.agePlaceholder")}
            style={styles.input}
            accessibilityLabel={t("quote.profile.ageLabel")}
            accessibilityHint={t("quote.profile.agePlaceholder")}
          />

          <Text style={[styles.fieldLabel, rtlText]}>
            {t("quote.profile.bmiLabel")}
          </Text>
          <TextInput
            value={bmiStr}
            onChangeText={setBmiStr}
            keyboardType="decimal-pad"
            placeholder={t("quote.profile.bmiPlaceholder")}
            style={styles.input}
            accessibilityLabel={t("quote.profile.bmiLabel")}
            accessibilityHint={t("quote.profile.bmiHint")}
          />
          <MutedText style={[styles.fieldHelp, rtlText]}>
            {t("quote.profile.bmiHelp")}
          </MutedText>

          <Text style={[styles.sectionLabel, rtlText]}>
            {t("quote.profile.flagsTitle")}
          </Text>
          <MutedText style={[styles.sectionHelp, rtlText]}>
            {t("quote.profile.flagsHelp")}
          </MutedText>
          {TOGGLE_FLAGS.map(({ key, labelKey }) => (
            <ToggleRow
              key={key}
              label={t(labelKey)}
              value={Boolean(profile[key])}
              onPress={() =>
                patchProfile({
                  [key]: !profile[key],
                } as Partial<HealthTourismProfile>)
              }
              rtl={Boolean(rtlText)}
            />
          ))}
        </Card>

        <View style={styles.actions}>
          <SecondaryButton onPress={() => setStep("browse")}>
            {t("common.back")}
          </SecondaryButton>
          <PrimaryButton
            onPress={handleSubmit}
            disabled={loading}
            style={styles.cta}
            accessibilityLabel={t("quote.profile.submit")}
          >
            {loading ? t("common.loading") : t("quote.profile.submit")}
          </PrimaryButton>
        </View>
      </ScrollView>
    </ScreenContainer>
  );
}

function ToggleRow({
  label,
  value,
  onPress,
  rtl,
}: {
  label: string;
  value: boolean;
  onPress: () => void;
  rtl: boolean;
}) {
  const rtlText = rtl ? RTL_TEXT_STYLE : undefined;
  return (
    <Pressable
      style={styles.toggleRow}
      onPress={onPress}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: value }}
      accessibilityLabel={label}
    >
      <View style={[styles.checkbox, value && styles.checkboxChecked]}>
        {value ? <Text style={styles.checkmark}>✓</Text> : null}
      </View>
      <Text style={[styles.toggleLabel, rtlText]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: tokens.spacing.lg,
  },
  scroll: {
    paddingBottom: tokens.spacing.xxl,
  },
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
  subtitle: {
    marginBottom: tokens.spacing.md,
  },
  card: {
    marginBottom: tokens.spacing.lg,
  },
  fieldLabel: {
    ...tokens.typography.h2,
    marginBottom: tokens.spacing.xs,
  },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    borderRadius: tokens.radius.md,
    backgroundColor: tokens.colors.surface,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    marginBottom: tokens.spacing.md,
    fontSize: 16,
    color: tokens.colors.textPrimary,
  },
  fieldHelp: {
    marginTop: -tokens.spacing.sm,
    marginBottom: tokens.spacing.md,
  },
  sectionLabel: {
    ...tokens.typography.h2,
    marginTop: tokens.spacing.lg,
    marginBottom: tokens.spacing.xs,
  },
  sectionHelp: {
    marginBottom: tokens.spacing.sm,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: tokens.spacing.sm,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: tokens.radius.sm,
    borderWidth: 2,
    borderColor: tokens.colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginRight: tokens.spacing.sm,
    backgroundColor: tokens.colors.surface,
  },
  checkboxChecked: {
    backgroundColor: tokens.colors.primary,
    borderColor: tokens.colors.primary,
  },
  checkmark: {
    color: "#FFFFFF",
    fontSize: 14,
    lineHeight: 14,
    fontWeight: "700",
  },
  toggleLabel: {
    ...tokens.typography.body,
    flex: 1,
  },
  actions: {
    flexDirection: "row",
    gap: tokens.spacing.md,
    marginTop: tokens.spacing.md,
  },
  cta: {
    flex: 1,
  },
});
