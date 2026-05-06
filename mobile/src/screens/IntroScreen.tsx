import React, { useMemo, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useTriageStore } from "@/src/state/triageStore";
import { PRIVACY_URL } from "@/src/config/runtime";
import { useTokens } from "@/src/ui/useTokens";
import {
  Card,
  Divider,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
} from "@/src/ui/primitives";

// Consent gate. The Stitch design requires three independent acknowledgments
// before the user enters the triage flow: terms, KVKK explicit consent for
// processing health data (KVKK 6. madde — özel kategori), and age (13+).
//
// Internally the triageStore still tracks a single `acceptIntro` boolean —
// we surface three switches in the UI for transparency + KVKK compliance,
// but only call `setAcceptIntro(true)` once all three are checked. Future
// work can split the store flag into a per-clause record if Privacy team
// asks for individual audit trails.

type ConsentSlot = {
  key: "terms" | "kvkk" | "age";
  labelKey: string;
  hintKey?: string;
};

const CONSENTS: ConsentSlot[] = [
  { key: "terms", labelKey: "intro.acceptTerms" },
  { key: "kvkk", labelKey: "intro.acceptKvkk", hintKey: "intro.acceptKvkkHint" },
  { key: "age", labelKey: "intro.acceptAge" },
];

export default function IntroScreen() {
  const [checked, setChecked] = useState<Record<ConsentSlot["key"], boolean>>({
    terms: false,
    kvkk: false,
    age: false,
  });
  const { t, isRTL } = useI18n();
  const setAcceptIntro = useTriageStore((s) => s.setAcceptIntro);
  const tokens = useTokens();
  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  const allAccepted = checked.terms && checked.kvkk && checked.age;

  const styles = useMemo(
    () =>
      StyleSheet.create({
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
        consentRow: {
          flexDirection: "row",
          alignItems: "flex-start",
          marginBottom: tokens.spacing.md,
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
          marginTop: 2, // align with first line of multi-line label
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
        consentTextWrap: {
          flex: 1,
        },
        consentLabel: {
          ...tokens.typography.bodySmall,
          color: tokens.colors.textPrimary,
        },
        consentHint: {
          ...tokens.typography.caption,
          color: tokens.colors.textMuted,
          marginTop: 2,
        },
        ctaButton: {
          marginTop: tokens.spacing.sm,
          borderRadius: tokens.radius.lg,
        },
        htButton: {
          borderRadius: tokens.radius.lg,
          marginTop: tokens.spacing.sm,
        },
        footer: {
          marginTop: tokens.spacing.lg,
          textAlign: "center",
        },
        footerLinks: {
          flexDirection: "row",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: tokens.spacing.md,
          marginTop: tokens.spacing.md,
        },
        languageLink: {
          paddingVertical: tokens.spacing.sm,
          paddingHorizontal: tokens.spacing.md,
          alignSelf: "center",
        },
        languageLinkText: {
          ...tokens.typography.bodySmall,
          color: tokens.colors.primary,
          textDecorationLine: "underline",
        },
      }),
    [tokens],
  );

  return (
    <ScreenContainer style={styles.container}>
      <View style={styles.centerWrap}>
        <Card style={styles.card}>
          <Text style={[styles.title, rtlText]}>{t("intro.title")}</Text>
          <Text style={[styles.subtitle, rtlText]}>{t("intro.subtitle")}</Text>

          <Divider />

          <Text style={[styles.body, rtlText]}>{t("intro.body")}</Text>

          {CONSENTS.map((slot) => {
            const isChecked = checked[slot.key];
            return (
              <Pressable
                key={slot.key}
                style={styles.consentRow}
                onPress={() =>
                  setChecked((prev) => ({ ...prev, [slot.key]: !prev[slot.key] }))
                }
                accessibilityRole="checkbox"
                accessibilityState={{ checked: isChecked }}
                accessibilityLabel={t(slot.labelKey)}
              >
                <View
                  style={[
                    styles.checkbox,
                    isChecked && styles.checkboxChecked,
                  ]}
                >
                  {isChecked ? <Text style={styles.checkmark}>✓</Text> : null}
                </View>
                <View style={styles.consentTextWrap}>
                  <Text style={[styles.consentLabel, rtlText]}>
                    {t(slot.labelKey)}
                  </Text>
                  {slot.hintKey ? (
                    <Text style={[styles.consentHint, rtlText]}>
                      {t(slot.hintKey)}
                    </Text>
                  ) : null}
                </View>
              </Pressable>
            );
          })}

          <PrimaryButton
            disabled={!allAccepted}
            onPress={() => setAcceptIntro(true)}
            style={styles.ctaButton}
            accessibilityRole="button"
            accessibilityLabel={t("intro.start")}
          >
            {t("intro.start")}
          </PrimaryButton>

          <SecondaryButton
            onPress={() => router.push("/quote")}
            style={styles.htButton}
            accessibilityRole="button"
            accessibilityLabel={t("intro.healthTourismCta")}
          >
            {t("intro.healthTourismCta")}
          </SecondaryButton>
        </Card>

        <MutedText style={[styles.footer, rtlText]}>
          {t("intro.emergencyNote")}
        </MutedText>
        <View style={styles.footerLinks}>
          <Pressable
            style={styles.languageLink}
            onPress={() => router.push("/language")}
            accessibilityRole="button"
            accessibilityLabel={t("languages.title")}
          >
            <Text style={[styles.languageLinkText, rtlText]}>
              {t("languages.title")}
            </Text>
          </Pressable>
          {PRIVACY_URL ? (
            <Pressable
              style={styles.languageLink}
              onPress={() => Linking.openURL(PRIVACY_URL)}
              accessibilityRole="link"
              accessibilityLabel={t("intro.privacyLink")}
            >
              <Text style={[styles.languageLinkText, rtlText]}>
                {t("intro.privacyLink")}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </ScreenContainer>
  );
}
