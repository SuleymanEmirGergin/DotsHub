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

export default function EmergencyScreen() {
  const emergency = useTriageStore((s) => s.emergency)!;
  const resetSession = useTriageStore((s) => s.resetSession);

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
          <SectionTitle style={styles.title}>Acil Değerlendirme Gerekebilir</SectionTitle>
          <Text style={styles.reason}>{emergency.reason_tr}</Text>

          <View style={styles.divider} />

          {emergency.instructions_tr.map((inst, i) => (
            <Text key={i} style={styles.instruction}>
              • {inst}
            </Text>
          ))}
        </Card>

        <DangerButton style={styles.buttonSpacing} onPress={call112}>
          112'yi Ara
        </DangerButton>

        <PrimaryButton style={styles.buttonSpacing} onPress={shareAlert}>
          Yakınıma Haber Ver
        </PrimaryButton>

        <SecondaryButton onPress={resetSession}>Yeni Değerlendirme</SecondaryButton>
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
    borderColor: "#F1B5B5",
    backgroundColor: "#FFF8F8",
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
    backgroundColor: "#F2D4D4",
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
