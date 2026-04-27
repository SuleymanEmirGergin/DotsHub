import React, { useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useTriageStore } from "@/src/state/triageStore";
import { PRIVACY_URL } from "@/src/config/runtime";
import { tokens } from "@/src/ui/designTokens";
import { getDeviceId } from "@/utils/deviceId";
import { recordIntroConsents } from "@/src/api/consentClient";
import {
  Card,
  Divider,
  MutedText,
  PrimaryButton,
  ScreenContainer,
} from "@/src/ui/primitives";

// Versions tracked on the mobile side. Must match backend config:
//   PRIVACY_NOTICE_VERSION, CONSENT_VERSION_TERMS_GENERAL,
//   CONSENT_VERSION_HEALTH_DATA in app/core/config.py.
// When bumping, edit both sides in the same PR.
const NOTICE_VERSION = "v0.2";
const TERMS_VERSION = "v1.0";
const HEALTH_DATA_VERSION = "v1.0";

export default function IntroScreen() {
  const [termsChecked, setTermsChecked] = useState(false);
  const [healthChecked, setHealthChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t, locale, isRTL } = useI18n();
  const setAcceptIntro = useTriageStore((s) => s.setAcceptIntro);
  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  const bothChecked = termsChecked && healthChecked;

  const onStart = async () => {
    if (!bothChecked || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const deviceId = getDeviceId();
      if (!deviceId) {
        // Should not happen on a real device — getDeviceId always
        // resolves something. Treat as a recoverable error so the
        // user retries rather than getting stuck.
        throw new Error("device_id_missing");
      }
      await recordIntroConsents({
        device_id: deviceId,
        locale,
        terms_version: TERMS_VERSION,
        health_data_version: HEALTH_DATA_VERSION,
        notice_version: NOTICE_VERSION,
      });
      setAcceptIntro(true);
    } catch {
      setError(t("intro.consentError"));
      setSubmitting(false);
    }
  };

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

          <ConsentCheckbox
            checked={termsChecked}
            onToggle={() => setTermsChecked((p) => !p)}
            label={t("intro.consentTermsLabel")}
            rtlText={rtlText}
          />

          <ConsentCheckbox
            checked={healthChecked}
            onToggle={() => setHealthChecked((p) => !p)}
            label={t("intro.consentHealthLabel")}
            hint={t("intro.consentHealthHint")}
            rtlText={rtlText}
          />

          {error ? (
            <Text style={[styles.errorText, rtlText]} accessibilityRole="alert">
              {error}
            </Text>
          ) : null}

          <PrimaryButton
            disabled={!bothChecked || submitting}
            onPress={onStart}
            style={styles.ctaButton}
            accessibilityRole="button"
            accessibilityLabel={t("intro.start")}
          >
            {submitting ? t("intro.consentSubmitting") : t("intro.start")}
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

function ConsentCheckbox({
  checked,
  onToggle,
  label,
  hint,
  rtlText,
}: {
  checked: boolean;
  onToggle: () => void;
  label: string;
  hint?: string;
  rtlText: typeof RTL_TEXT_STYLE | undefined;
}) {
  return (
    <View style={styles.consentBlock}>
      <Pressable
        style={styles.checkRow}
        onPress={onToggle}
        accessibilityRole="checkbox"
        accessibilityState={{ checked }}
        accessibilityLabel={label}
      >
        <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
          {checked ? <Text style={styles.checkmark}>✓</Text> : null}
        </View>
        <Text style={[styles.checkLabel, rtlText]}>{label}</Text>
      </Pressable>
      {hint ? (
        <Text style={[styles.consentHint, rtlText]}>{hint}</Text>
      ) : null}
    </View>
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
  consentBlock: {
    marginBottom: tokens.spacing.md,
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
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
    flexShrink: 1,
  },
  consentHint: {
    ...tokens.typography.caption,
    color: tokens.colors.textSecondary,
    marginTop: tokens.spacing.xs,
    marginLeft: 32,
  },
  errorText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.error,
    marginTop: tokens.spacing.sm,
    marginBottom: tokens.spacing.sm,
  },
  ctaButton: {
    marginTop: tokens.spacing.md,
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
    paddingHorizontal: tokens.spacing.md,
    alignSelf: "center",
  },
  languageLinkText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.primary,
    textDecorationLine: "underline",
  },
});
