import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { tokens } from "@/src/ui/designTokens";

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x));
}

export default function ConfidenceBar({
  value,
  label,
  hint,
}: {
  value: number;
  label: string;
  hint?: string;
}) {
  const v = clamp01(value);
  const pct = Math.round(v * 100);

  const barColor =
    label === "Yüksek" ? "#2E7D32" : label === "Orta" ? "#F9A825" : "#E53935";

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Güven Seviyesi</Text>
        <Text style={[styles.label, { color: barColor }]}>
          {label} ({pct}%)
        </Text>
      </View>

      <View style={styles.barBg}>
        <View
          style={[
            styles.barFill,
            { width: `${pct}%`, backgroundColor: barColor },
          ]}
        />
      </View>

      <Text style={styles.hint}>
        {hint ?? "Bu oran, verilen bilgilere göre yönlendirme güvenini gösterir. Teşhis değildir."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: tokens.colors.surface,
    borderRadius: tokens.radius.lg,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    padding: tokens.spacing.lg,
    ...tokens.shadow.soft,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: tokens.spacing.sm,
    gap: tokens.spacing.sm,
  },
  title: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textPrimary,
    fontWeight: "600",
  },
  label: {
    ...tokens.typography.bodySmall,
    fontWeight: "700",
  },
  barBg: {
    height: 10,
    borderRadius: tokens.radius.pill,
    backgroundColor: tokens.colors.surfaceAlt,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: tokens.radius.pill,
  },
  hint: {
    marginTop: tokens.spacing.sm,
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
  },
});
