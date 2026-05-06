/**
 * Step 6 — Lead accepted. Confirmation + "what happens next".
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

export default function LeadSuccessScreen({ onExit }: Props) {
  const { t, isRTL } = useI18n();
  const lead = useQuoteStore((s) => s.leadResult);
  const reset = useQuoteStore((s) => s.reset);
  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.iconWrap}>
          <Text style={styles.icon}>✓</Text>
        </View>
        <Text style={[styles.title, rtlText]}>{t("quote.success.title")}</Text>
        <MutedText style={[styles.subtitle, rtlText]}>
          {lead?.next_steps_tr ?? t("quote.success.fallback")}
        </MutedText>

        {lead ? (
          <Card style={styles.card}>
            <Text style={[styles.detailLabel, rtlText]}>
              {t("quote.success.procedureLabel")}
            </Text>
            <Text style={[styles.detailValue, rtlText]}>
              {lead.procedure_name_tr}
            </Text>

            <Text style={[styles.detailLabel, rtlText]}>
              {t("quote.success.clinicLabel")}
            </Text>
            <Text style={[styles.detailValue, rtlText]}>{lead.clinic_name}</Text>

            {lead.quoted_price_eur != null ? (
              <>
                <Text style={[styles.detailLabel, rtlText]}>
                  {t("quote.success.priceLabel")}
                </Text>
                <Text style={[styles.detailValue, rtlText]}>
                  €{lead.quoted_price_eur} EUR
                </Text>
              </>
            ) : null}

            <Text style={[styles.detailLabel, rtlText]}>
              {t("quote.success.leadIdLabel")}
            </Text>
            <Text style={[styles.detailValue, styles.monoText, rtlText]}>
              {lead.lead_id}
            </Text>
          </Card>
        ) : null}

        <View style={styles.actions}>
          <SecondaryButton
            onPress={() => {
              reset();
              onExit();
            }}
          >
            {t("quote.success.exitCta")}
          </SecondaryButton>
          <PrimaryButton
            onPress={() => reset()}
            style={styles.cta}
            accessibilityLabel={t("quote.success.newCta")}
          >
            {t("quote.success.newCta")}
          </PrimaryButton>
        </View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: tokens.spacing.xl },
  scroll: { paddingBottom: tokens.spacing.xxl, alignItems: "stretch" },
  iconWrap: {
    alignSelf: "center",
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: tokens.colors.success,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: tokens.spacing.md,
  },
  icon: { color: "#FFFFFF", fontSize: 32, fontWeight: "700" },
  title: {
    ...tokens.typography.title,
    textAlign: "center",
    marginBottom: tokens.spacing.sm,
  },
  subtitle: { textAlign: "center", marginBottom: tokens.spacing.lg },
  card: { marginBottom: tokens.spacing.lg },
  detailLabel: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    marginTop: tokens.spacing.sm,
    fontWeight: "600",
    textTransform: "uppercase",
  },
  detailValue: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
  },
  monoText: { fontFamily: "Courier" },
  actions: { flexDirection: "row", gap: tokens.spacing.md },
  cta: { flex: 1 },
});
