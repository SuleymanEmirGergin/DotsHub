import React from "react";
import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import Constants from "expo-constants";
import { useI18n } from "@/i18n/I18nProvider";
import type { Locale } from "@/i18n";
import { SUPPORTED_LOCALES } from "@/i18n";
import { tokens, screenPadding } from "@/src/ui/designTokens";
import { Card, MutedText, ScreenContainer } from "@/src/ui/primitives";

/**
 * SettingsScreen — consolidates app-level user controls into one
 * reachable-from-chat place. Before this existed, Privacy / Terms
 * were only referenced in .env (as URLs the app never actually
 * opened), language switching was on Intro only, and the app's
 * version was invisible to support requests.
 *
 * Sections (top to bottom):
 *   1. Language — row per supported locale, tap to set
 *   2. Legal — Privacy + Terms URLs from env (or sensible defaults)
 *   3. About — app version from expo-constants + build id
 *   4. Contact — mailto link to support email
 *
 * Style note: reused ScreenContainer + Card primitives so the
 * chrome (header, safe area padding, shadow) matches History and
 * Intro. No new visual patterns introduced — B6 Skeleton + tokens
 * commit already set the baseline.
 */

const PRIVACY_URL_DEFAULT = "https://triaige.vercel.app/privacy";
const TERMS_URL_DEFAULT = "https://triaige.vercel.app/terms";
const CONTACT_EMAIL = "emirgergin21@gmail.com";

type Props = {
  onBack: () => void;
};

export default function SettingsScreen({ onBack }: Props) {
  const { t, locale, setLocale } = useI18n();

  // Expo Constants surfaces the app.config.ts `expo.version` and a
  // build identifier on production binaries. During local dev both
  // fall back to sensible placeholders — never crashes.
  const expoConfig = Constants.expoConfig ?? null;
  const version = expoConfig?.version ?? "dev";
  // `runtimeVersion` can be either a string (when pinned directly) OR
  // a policy object like `{ policy: "appVersion" }`. Collapse both to
  // a string so React can render it — policies read as e.g.
  // "policy:appVersion" which is fine for a debug label.
  const runtime = expoConfig?.runtimeVersion;
  const runtimeStr =
    typeof runtime === "string"
      ? runtime
      : runtime && typeof runtime === "object" && "policy" in runtime
        ? `policy:${(runtime as { policy: string }).policy}`
        : null;
  const buildId =
    (Constants as unknown as { nativeBuildVersion?: string }).nativeBuildVersion ||
    runtimeStr ||
    "local";

  // Env-driven URLs (set via mobile/.env). Fall back to production
  // dashboard URL so the links are never broken even if an operator
  // forgets to set the env — privacy/terms pages live at the same
  // Vercel deployment.
  const privacyUrl =
    (process.env.EXPO_PUBLIC_PRIVACY_URL as string | undefined) ?? PRIVACY_URL_DEFAULT;
  const termsUrl =
    (process.env.EXPO_PUBLIC_TERMS_URL as string | undefined) ?? TERMS_URL_DEFAULT;

  async function openLink(url: string) {
    try {
      await Linking.openURL(url);
    } catch {
      // Alert is cross-platform + accessible; preferable to console
      // when the user expected a link to open and it didn't.
      Alert.alert(t("common.error"), t("settings.linkError"));
    }
  }

  async function openEmail() {
    await openLink(`mailto:${CONTACT_EMAIL}`);
  }

  return (
    <ScreenContainer style={styles.container}>
      {/* Header — mirrors HistoryScreen for consistency. Back button
          on left, title centred, spacer on right so title stays
          visually centred regardless of back-button width. */}
      <View style={styles.header}>
        <Pressable
          onPress={onBack}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel={t("settings.back")}
        >
          <Text style={styles.backText}>{t("settings.back")}</Text>
        </Pressable>
        <Text style={styles.title}>{t("settings.title")}</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {/* ─── Language ─── */}
        <SectionHeader>{t("settings.languageSection")}</SectionHeader>
        <Card>
          {SUPPORTED_LOCALES.map((code, i) => {
            const isActive = locale === code;
            const isLast = i === SUPPORTED_LOCALES.length - 1;
            return (
              <Pressable
                key={code}
                onPress={() => setLocale(code as Locale)}
                style={({ pressed }) => [
                  styles.row,
                  !isLast && styles.rowBorder,
                  pressed && styles.rowPressed,
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: isActive }}
                accessibilityLabel={labelForLocale(code as Locale)}
              >
                <Text style={styles.rowLabel}>{labelForLocale(code as Locale)}</Text>
                {isActive && <Text style={styles.check}>✓</Text>}
              </Pressable>
            );
          })}
        </Card>

        {/* ─── Legal (Privacy + Terms) ─── */}
        <SectionHeader>{t("settings.legalSection")}</SectionHeader>
        <Card>
          <Pressable
            onPress={() => openLink(privacyUrl)}
            style={({ pressed }) => [
              styles.row,
              styles.rowBorder,
              pressed && styles.rowPressed,
            ]}
            accessibilityRole="link"
            accessibilityLabel={t("settings.privacy")}
          >
            <Text style={styles.rowLabel}>{t("settings.privacy")}</Text>
            <Text style={styles.chevron}>›</Text>
          </Pressable>
          <Pressable
            onPress={() => openLink(termsUrl)}
            style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            accessibilityRole="link"
            accessibilityLabel={t("settings.terms")}
          >
            <Text style={styles.rowLabel}>{t("settings.terms")}</Text>
            <Text style={styles.chevron}>›</Text>
          </Pressable>
        </Card>

        {/* ─── About ─── */}
        <SectionHeader>{t("settings.aboutSection")}</SectionHeader>
        <Card>
          <View style={[styles.row, styles.rowBorder]}>
            <Text style={styles.rowLabel}>{t("settings.version")}</Text>
            <MutedText style={styles.rowValue}>{version}</MutedText>
          </View>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>{t("settings.buildId")}</Text>
            <MutedText style={styles.rowValue}>{buildId}</MutedText>
          </View>
        </Card>

        {/* ─── Contact ─── */}
        <SectionHeader>{t("settings.contactSection")}</SectionHeader>
        <Card>
          <Pressable
            onPress={openEmail}
            style={({ pressed }) => [
              styles.row,
              styles.rowBorder,
              pressed && styles.rowPressed,
            ]}
            accessibilityRole="link"
            accessibilityLabel={`${t("settings.contactEmail")}: ${CONTACT_EMAIL}`}
          >
            <Text style={styles.rowLabel}>{t("settings.contactEmail")}</Text>
            <MutedText style={styles.rowValue}>{CONTACT_EMAIL}</MutedText>
          </Pressable>
          <View style={styles.row}>
            <MutedText style={styles.supportLine}>
              {t("settings.supportLine")}
            </MutedText>
          </View>
        </Card>
      </ScrollView>
    </ScreenContainer>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return <Text style={styles.sectionHeader}>{children}</Text>;
}

/**
 * Map locale code → native-name label. Hard-coded on purpose: i18n
 * keys would duplicate what the user obviously expects in their own
 * language for each list row.
 */
function labelForLocale(code: Locale): string {
  switch (code) {
    case "tr":
      return "Türkçe";
    case "en":
      return "English";
    case "de":
      return "Deutsch";
    case "ru":
      return "Русский";
    case "ar":
      return "العربية";
    default:
      return code;
  }
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 0,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: screenPadding,
    paddingVertical: tokens.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
    backgroundColor: tokens.colors.surface,
  },
  backBtn: {
    width: 72,
  },
  backText: {
    ...tokens.typography.body,
    color: tokens.colors.primary,
    fontWeight: "600",
  },
  title: {
    ...tokens.typography.h2,
    textAlign: "center",
    flex: 1,
  },
  scroll: {
    padding: screenPadding,
    paddingBottom: tokens.spacing.xxl,
  },
  sectionHeader: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: tokens.spacing.lg,
    marginBottom: tokens.spacing.sm,
    paddingHorizontal: tokens.spacing.sm,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: tokens.spacing.lg,
    paddingVertical: tokens.spacing.md,
    minHeight: 52,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: tokens.colors.border,
  },
  rowPressed: {
    backgroundColor: tokens.colors.surfaceAlt,
  },
  rowLabel: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
    flex: 1,
  },
  rowValue: {
    fontSize: 14,
  },
  check: {
    ...tokens.typography.body,
    color: tokens.colors.success,
    fontWeight: "700",
    marginLeft: tokens.spacing.sm,
  },
  chevron: {
    color: tokens.colors.textMuted,
    fontSize: 22,
    lineHeight: 22,
    marginLeft: tokens.spacing.sm,
  },
  supportLine: {
    fontSize: 13,
    lineHeight: 18,
    flex: 1,
  },
});
