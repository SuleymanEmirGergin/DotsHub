import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTriageStore } from "@/src/state/triageStore";
import { tokens } from "@/src/ui/designTokens";
import {
  Card,
  Divider,
  MutedText,
  PrimaryButton,
  ScreenContainer,
} from "@/src/ui/primitives";

export default function IntroScreen() {
  const [checked, setChecked] = useState(false);
  const setAcceptIntro = useTriageStore((s) => s.setAcceptIntro);

  return (
    <ScreenContainer style={styles.container}>
      <View style={styles.centerWrap}>
        <Card style={styles.card}>
          <Text style={styles.title}>Ön Sağlık Değerlendirme</Text>
          <Text style={styles.subtitle}>
            Bu uygulama teşhis koymaz. Şikayetlerini anlamaya ve doğru branşa
            yönlendirmeye yardımcı olur.
          </Text>

          <Divider />

          <Text style={styles.body}>
            Belirtilerini tarif edeceksin, sana birkaç kısa soru soracağız ve
            hangi uzmanlık alanına gitmen gerektiğini önereceğiz.
          </Text>

          <Pressable
            style={styles.checkRow}
            onPress={() => setChecked((prev) => !prev)}
          >
            <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
              {checked ? <Text style={styles.checkmark}>✓</Text> : null}
            </View>
            <Text style={styles.checkLabel}>Anladım, kabul ediyorum</Text>
          </Pressable>

          <PrimaryButton
            disabled={!checked}
            onPress={() => setAcceptIntro(true)}
            style={styles.ctaButton}
          >
            Başla
          </PrimaryButton>
        </Card>

        <MutedText style={styles.footer}>Acil durumlarda 112'yi arayın.</MutedText>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
  },
  centerWrap: {
    flex: 1,
    justifyContent: "center",
  },
  card: {
    paddingVertical: tokens.spacing.xxl,
  },
  title: {
    ...tokens.typography.title,
    marginBottom: tokens.spacing.sm,
  },
  subtitle: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
  },
  body: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
    marginBottom: tokens.spacing.lg,
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: tokens.spacing.lg,
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
  checkLabel: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textPrimary,
  },
  ctaButton: {
    borderRadius: tokens.radius.lg,
  },
  footer: {
    marginTop: tokens.spacing.lg,
    textAlign: "center",
  },
});
