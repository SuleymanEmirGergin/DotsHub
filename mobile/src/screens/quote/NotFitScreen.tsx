/**
 * EMERGENCY-style screen — fit-to-travel block.
 *
 * The patient's profile triggered a `block` rule in fit_to_travel
 * (e.g., recent_mi for plastic surgery). The backend returned an
 * EMERGENCY envelope with reason + recommendation. We surface them
 * prominently and tell the patient what to do next; no link to the
 * quote/itinerary path because they cannot travel safely.
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

type Props = {
  onExit: () => void;
};

export default function NotFitScreen({ onExit }: Props) {
  const { t, isRTL } = useI18n();
  const notFit = useQuoteStore((s) => s.notFit);
  const setStep = useQuoteStore((s) => s.setStep);
  const reset = useQuoteStore((s) => s.reset);

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.iconWrap}>
          <Text style={styles.icon}>!</Text>
        </View>
        <Text style={[styles.title, rtlText]}>{t("quote.notFit.title")}</Text>
        <Text style={[styles.subtitle, rtlText]}>
          {notFit?.procedure_name_tr ?? ""}
        </Text>

        <Card style={styles.reasonCard}>
          <Text style={[styles.reasonLabel, rtlText]}>
            {t("quote.notFit.reasonLabel")}
          </Text>
          <Text style={[styles.reasonText, rtlText]}>
            {notFit?.reason_tr ?? t("quote.notFit.fallbackReason")}
          </Text>
          {notFit?.instructions_tr && notFit.instructions_tr.length > 0 ? (
            <>
              <Text style={[styles.reasonLabel, rtlText]}>
                {t("quote.notFit.instructionsLabel")}
              </Text>
              {notFit.instructions_tr.map((line, idx) => (
                <Text key={idx} style={[styles.instructionLine, rtlText]}>
                  • {line}
                </Text>
              ))}
            </>
          ) : null}
        </Card>

        <MutedText style={[styles.disclaimer, rtlText]}>
          {t("quote.notFit.disclaimer")}
        </MutedText>

        <View style={styles.actions}>
          <SecondaryButton onPress={() => setStep("profile")}>
            {t("quote.notFit.adjustProfile")}
          </SecondaryButton>
          <PrimaryButton
            onPress={() => {
              reset();
              onExit();
            }}
            style={styles.cta}
          >
            {t("quote.notFit.exitCta")}
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
    marginBottom: tokens.spacing.xs,
  },
  subtitle: {
    ...tokens.typography.h2,
    textAlign: "center",
    color: tokens.colors.textSecondary,
    marginBottom: tokens.spacing.lg,
  },
  reasonCard: {
    backgroundColor: tokens.colors.errorBg,
    borderColor: tokens.colors.errorBorder,
    marginBottom: tokens.spacing.md,
  },
  reasonLabel: {
    ...tokens.typography.caption,
    color: tokens.colors.error,
    fontWeight: "700",
    textTransform: "uppercase",
    marginTop: tokens.spacing.sm,
  },
  reasonText: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    marginTop: 2,
    marginBottom: tokens.spacing.sm,
  },
  instructionLine: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textPrimary,
    marginVertical: 2,
  },
  disclaimer: {
    textAlign: "center",
    marginVertical: tokens.spacing.md,
  },
  actions: { flexDirection: "row", gap: tokens.spacing.md, marginTop: tokens.spacing.md },
  cta: { flex: 1 },
});
