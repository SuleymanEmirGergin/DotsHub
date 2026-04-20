import React from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { useTriageStore } from "@/src/state/triageStore";
import { tokens } from "@/src/ui/designTokens";
import {
  Card,
  DangerButton,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
  SectionTitle,
} from "@/src/ui/primitives";
import { useI18n } from "@/i18n/I18nProvider";

export default function EmergencyScreen() {
  const emergency = useTriageStore((s) => s.emergency)!;
  const resetSession = useTriageStore((s) => s.resetSession);
  const { t } = useI18n();

  function call112() {
    Linking.openURL("tel:112");
  }

  function shareAlert() {
    const msg = `ACİL: ${emergency.reason_tr}\n\n${emergency.instructions_tr.join("\n")}`;
    Linking.openURL(`sms:?body=${encodeURIComponent(msg)}`);
  }

  return (
    <ScreenContainer>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Card style={styles.alertCard}>
          <View style={styles.iconWrap}>
            <Text style={styles.icon}>⚠</Text>
          </View>
          <SectionTitle style={styles.title}>{t("emergency.title")}</SectionTitle>
          <Text style={styles.reason}>{emergency.reason_tr}</Text>

          <View style={styles.divider} />

          {emergency.instructions_tr.map((inst, i) => (
            <Text key={i} style={styles.instruction}>
              • {inst}
            </Text>
          ))}
        </Card>

        <DangerButton style={styles.buttonSpacing} onPress={call112}>
          {t("emergency.call112")}
        </DangerButton>

        <PrimaryButton style={styles.buttonSpacing} onPress={shareAlert}>
          {t("emergency.notifyContact")}
        </PrimaryButton>

        <SecondaryButton onPress={resetSession}>{t("common.newAssessment")}</SecondaryButton>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingVertical: tokens.spacing.xl,
  },
  alertCard: {
    borderColor: tokens.colors.errorBorder,
    backgroundColor: tokens.colors.errorBg,
    marginBottom: tokens.spacing.lg,
  },
  iconWrap: {
    alignItems: "center",
    marginBottom: tokens.spacing.sm,
  },
  icon: {
    fontSize: 42,
    lineHeight: 46,
  },
  title: {
    color: tokens.colors.error,
    textAlign: "center",
  },
  reason: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    textAlign: "center",
    marginBottom: tokens.spacing.sm,
  },
  divider: {
    height: 1,
    backgroundColor: tokens.colors.errorDivider,
    marginVertical: tokens.spacing.md,
  },
  instruction: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    marginBottom: tokens.spacing.xs,
  },
  buttonSpacing: {
    marginBottom: tokens.spacing.sm,
  },
});
