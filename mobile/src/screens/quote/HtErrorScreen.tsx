/**
 * ERROR screen for the HT flow.
 *
 * Backend returned an ERROR envelope (procedure unresolved, no partner
 * clinic, network blip, etc.). Show the message and let the user
 * retry from the most-relevant prior step.
 */
import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
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

export default function HtErrorScreen() {
  const { t, isRTL } = useI18n();
  const error = useQuoteStore((s) => s.error);
  const setStep = useQuoteStore((s) => s.setStep);
  const procedure = useQuoteStore((s) => s.procedure);

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  // Pick the most appropriate retry destination by error code.
  const retryTo: "browse" | "profile" | "lead" =
    error?.code === "PROCEDURE_UNRESOLVED" || error?.code === "PROCEDURE_UNKNOWN"
      ? "browse"
      : error?.code === "CLINIC_PROCEDURE_MISMATCH"
        ? "browse"
        : "profile";

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.iconWrap}>
          <Text style={styles.icon}>!</Text>
        </View>
        <Text style={[styles.title, rtlText]}>{t("error.title")}</Text>

        <Card style={styles.card}>
          <Text style={[styles.code, rtlText]}>
            {t("error.code")}: {error?.code ?? "UNKNOWN"}
          </Text>
          <Text style={[styles.message, rtlText]}>
            {error?.message_tr ?? t("error.fallbackMessage")}
          </Text>
        </Card>

        <View style={styles.actions}>
          <SecondaryButton
            onPress={() => setStep(procedure ? "profile" : "browse")}
          >
            {t("common.back")}
          </SecondaryButton>
          <PrimaryButton
            onPress={() => setStep(retryTo)}
            style={styles.cta}
            accessibilityLabel={t("common.retry")}
          >
            {t("common.retry")}
          </PrimaryButton>
        </View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: tokens.spacing.xl },
  scroll: { paddingBottom: tokens.spacing.xxl },
  iconWrap: {
    alignSelf: "center",
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: tokens.colors.error,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: tokens.spacing.md,
  },
  icon: { color: "#FFFFFF", fontSize: 36, fontWeight: "700" },
  title: {
    ...tokens.typography.title,
    textAlign: "center",
    marginBottom: tokens.spacing.md,
  },
  card: {
    backgroundColor: tokens.colors.errorBg,
    borderColor: tokens.colors.errorBorder,
    marginBottom: tokens.spacing.md,
  },
  code: {
    ...tokens.typography.caption,
    color: tokens.colors.error,
    fontWeight: "700",
    textTransform: "uppercase",
    marginBottom: tokens.spacing.xs,
  },
  message: { ...tokens.typography.body },
  actions: { flexDirection: "row", gap: tokens.spacing.md, marginTop: tokens.spacing.md },
  cta: { flex: 1 },
});
