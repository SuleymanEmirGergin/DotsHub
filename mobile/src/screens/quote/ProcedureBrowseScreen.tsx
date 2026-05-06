/**
 * Step 1 — pick a procedure.
 *
 * Renders categories + procedures from the local catalog (no network
 * round-trip). Tapping a row stores the selection and advances to the
 * profile step.
 */
import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useQuoteStore } from "@/src/state/quoteStore";
import {
  CATEGORIES,
  PROCEDURES,
  type Procedure,
  type ProcedureCategory,
} from "@/src/data/proceduresCatalog";
import { tokens } from "@/src/ui/designTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SectionTitle,
} from "@/src/ui/primitives";

type Props = {
  onExit: () => void;
};

const CATEGORY_LABEL_KEY: Record<ProcedureCategory, string> = {
  hair: "quote.category.hair",
  dental: "quote.category.dental",
  plastic_surgery: "quote.category.plastic_surgery",
  eye: "quote.category.eye",
  obesity: "quote.category.obesity",
  ivf: "quote.category.ivf",
};

export default function ProcedureBrowseScreen({ onExit }: Props) {
  const { t, locale, isRTL } = useI18n();
  const pickProcedure = useQuoteStore((s) => s.pickProcedure);
  const [activeCat, setActiveCat] = useState<ProcedureCategory | "all">("all");

  const filtered = useMemo(() => {
    if (activeCat === "all") return PROCEDURES;
    return PROCEDURES.filter((p) => p.category === activeCat);
  }, [activeCat]);

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  return (
    <ScreenContainer style={styles.container}>
      <View style={styles.header}>
        <Pressable
          onPress={onExit}
          style={styles.backLink}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Text style={[styles.backText, rtlText]}>← {t("common.back")}</Text>
        </Pressable>
        <Text style={[styles.title, rtlText]}>{t("quote.browse.title")}</Text>
        <MutedText style={[styles.subtitle, rtlText]}>
          {t("quote.browse.subtitle")}
        </MutedText>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipsRow}
      >
        <CategoryChip
          label={t("quote.category.all")}
          active={activeCat === "all"}
          onPress={() => setActiveCat("all")}
        />
        {CATEGORIES.map((c) => (
          <CategoryChip
            key={c}
            label={t(CATEGORY_LABEL_KEY[c])}
            active={activeCat === c}
            onPress={() => setActiveCat(c)}
          />
        ))}
      </ScrollView>

      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {filtered.map((p) => (
          <ProcedureRow
            key={p.id}
            procedure={p}
            onPress={() => pickProcedure(p)}
            label={p.name[locale as "tr" | "en" | "de" | "ru" | "ar"] ?? p.name.tr}
            recoveryLabel={t("quote.browse.recoveryDays")}
            stayLabel={t("quote.browse.stayDays")}
            indicativeLabel={t("quote.browse.indicativeFrom")}
            rtl={Boolean(rtlText)}
          />
        ))}
        {filtered.length === 0 ? (
          <MutedText style={[styles.emptyText, rtlText]}>
            {t("quote.browse.empty")}
          </MutedText>
        ) : null}
      </ScrollView>
    </ScreenContainer>
  );
}

function CategoryChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

function ProcedureRow({
  procedure,
  onPress,
  label,
  recoveryLabel,
  stayLabel,
  indicativeLabel,
  rtl,
}: {
  procedure: Procedure;
  onPress: () => void;
  label: string;
  recoveryLabel: string;
  stayLabel: string;
  indicativeLabel: string;
  rtl: boolean;
}) {
  const rtlText = rtl ? RTL_TEXT_STYLE : undefined;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label}, ${procedure.indicative_price_eur} EUR`}
      style={({ pressed }) => [
        styles.rowPressable,
        pressed && styles.rowPressed,
      ]}
    >
      <Card style={styles.row}>
        <Text style={[styles.rowTitle, rtlText]}>{label}</Text>
        <Text style={[styles.rowMeta, rtlText]}>
          {indicativeLabel}{" "}
          <Text style={styles.rowPrice}>€{procedure.indicative_price_eur}</Text>
        </Text>
        <Text style={[styles.rowMeta, rtlText]}>
          {stayLabel}: {procedure.duration_days.min_stay}–
          {procedure.duration_days.max_stay} • {recoveryLabel}:{" "}
          {procedure.duration_days.recovery_total}
        </Text>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: tokens.spacing.lg,
  },
  header: {
    paddingBottom: tokens.spacing.md,
  },
  backLink: {
    paddingVertical: tokens.spacing.xs,
    marginBottom: tokens.spacing.sm,
  },
  backText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
  },
  title: {
    ...tokens.typography.title,
    marginBottom: tokens.spacing.xs,
  },
  subtitle: {
    marginBottom: tokens.spacing.md,
  },
  chipsRow: {
    flexDirection: "row",
    gap: tokens.spacing.sm,
    paddingVertical: tokens.spacing.sm,
  },
  chip: {
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    borderRadius: tokens.radius.pill,
    backgroundColor: tokens.colors.surface,
    borderWidth: 1,
    borderColor: tokens.colors.border,
  },
  chipActive: {
    backgroundColor: tokens.colors.primary,
    borderColor: tokens.colors.primary,
  },
  chipText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
    fontWeight: "600",
  },
  chipTextActive: {
    color: "#FFFFFF",
  },
  list: {
    flex: 1,
    marginTop: tokens.spacing.sm,
  },
  listContent: {
    paddingBottom: tokens.spacing.xxl,
    gap: tokens.spacing.md,
  },
  rowPressable: {
    borderRadius: tokens.radius.xl,
  },
  rowPressed: {
    opacity: 0.85,
  },
  row: {
    paddingVertical: tokens.spacing.lg,
  },
  rowTitle: {
    ...tokens.typography.h2,
    marginBottom: tokens.spacing.xs,
  },
  rowMeta: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
    marginTop: 2,
  },
  rowPrice: {
    fontWeight: "700",
    color: tokens.colors.textPrimary,
  },
  emptyText: {
    textAlign: "center",
    marginTop: tokens.spacing.xl,
  },
});
