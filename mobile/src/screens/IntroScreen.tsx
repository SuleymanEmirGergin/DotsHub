import React, { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useTriageStore } from "@/src/state/triageStore";
import { PRIVACY_URL } from "@/src/config/runtime";
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
  const { t, isRTL } = useI18n();
  const setAcceptIntro = useTriageStore((s) => s.setAcceptIntro);
  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  return (
    <ScreenContainer style={styles.container}>
      <View style={styles.centerWrap}>
        <Card style={styles.card}>
          <Text style={[styles.title, rtlText]}>{t("intro.title")}</Text>
          <Text style={[styles.subtitle, rtlText]}>
            {t("intro.subtitle")}
          </Text>

          <Divider />

          <Text style={[styles.body, rtlText]}>
            {t("intro.body")}
          </Text>

          <Pressable
            style={styles.checkRow}
            onPress={() => setChecked((prev) => !prev)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked }}
            accessibilityLabel={t("intro.accept")}
          >
            <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
              {checked ? <Text style={styles.checkmark}>✓</Text> : null}
            </View>
            <Text style={[styles.checkLabel, rtlText]}>{t("intro.accept")}</Text>
          </Pressable>

          <PrimaryButton
            disabled={!checked}
            onPress={() => setAcceptIntro(true)}
            style={styles.ctaButton}
            accessibilityRole="button"
            accessibilityLabel={t("intro.start")}
          >
            {t("intro.start")}
          </PrimaryButton>
        </Card>

        <MutedText style={[styles.footer, rtlText]}>{t("intro.emergencyNote")}</MutedText>
        <View style={styles.footerLinks}>
          <Pressable
            style={styles.languageLink}
            onPress={() => router.push("/language")}
            accessibilityRole="button"
            accessibilityLabel={t("languages.title")}
          >
            <Text style={[styles.languageLinkText, rtlText]}>{t("languages.title")}</Text>
          </Pressable>
          {PRIVACY_URL ? (
            <Pressable
              style={styles.languageLink}
              onPress={() => Linking.openURL(PRIVACY_URL)}
              accessibilityRole="link"
              accessibilityLabel={t("intro.privacyLink")}
            >
              <Text style={[styles.languageLinkText, rtlText]}>{t("intro.privacyLink")}</Text>
            </Pressable>
          ) : null}
        </View>
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
  footerLinks: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: tokens.spacing.md,
    marginTop: tokens.spacing.md,
  },
  languageLink: {
    paddingVertical: tokens.spacing.sm,
    paddingVertical: tokens.spacing.sm,
    paddingHorizontal: tokens.spacing.md,
    alignSelf: "center",
  },
  languageLinkText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.primary,
    textDecorationLine: "underline",
  },
});
