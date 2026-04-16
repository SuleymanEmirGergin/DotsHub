import React, { useLayoutEffect } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { router, useNavigation } from "expo-router";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { SUPPORTED_LOCALES, type Locale } from "@/i18n/index";
import { ScreenContainer } from "@/src/ui/primitives";
import { tokens } from "@/src/ui/designTokens";

export default function LanguageScreen() {
  const { t, locale, setLocale, isRTL } = useI18n();
  const navigation = useNavigation();

  useLayoutEffect(() => {
    navigation.setOptions({ title: t("languages.title") });
  }, [navigation, t]);

  const onSelect = (code: Locale) => {
    setLocale(code);
    router.back();
  };

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;
  return (
    <ScreenContainer style={styles.container}>
      <Text style={[styles.title, rtlText]}>{t("languages.title")}</Text>
      <View style={styles.list}>
        {SUPPORTED_LOCALES.map((code) => (
          <Pressable
            key={code}
            style={[styles.row, locale === code && styles.rowSelected]}
            onPress={() => onSelect(code)}
          >
            <Text
              style={[
                styles.label,
                locale === code && styles.labelSelected,
                rtlText,
              ]}
            >
              {t(`languages.${code}`)}
            </Text>
            {locale === code ? (
              <Text style={styles.check}>✓</Text>
            ) : null}
          </Pressable>
        ))}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: tokens.spacing.lg,
  },
  title: {
    ...tokens.typography.title,
    marginBottom: tokens.spacing.lg,
  },
  list: {
    gap: tokens.spacing.xs,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: tokens.spacing.md,
    paddingHorizontal: tokens.spacing.lg,
    borderRadius: tokens.radius.md,
    backgroundColor: tokens.colors.surface,
  },
  rowSelected: {
    backgroundColor: tokens.colors.primary + "18",
    borderWidth: 1,
    borderColor: tokens.colors.primary,
  },
  label: {
    ...tokens.typography.body,
    color: tokens.colors.textPrimary,
  },
  labelSelected: {
    color: tokens.colors.primary,
    fontWeight: "600",
  },
  check: {
    color: tokens.colors.primary,
    fontSize: 16,
    fontWeight: "700",
  },
});
