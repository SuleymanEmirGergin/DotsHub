import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  FlatList,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  View,
  RefreshControl,
} from "react-native";
import { screenPadding } from "@/src/ui/designTokens";
import { useTokens } from "@/src/ui/useTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
  Badge,
} from "@/src/ui/primitives";
import { SessionCardSkeleton, SkeletonList } from "@/src/ui/Skeleton";
import { API_BASE } from "@/constants";
import { getDeviceId } from "@/utils/deviceId";
import { useI18n } from "@/i18n/I18nProvider";

type SessionItem = {
  id: string;
  created_at: string;
  envelope_type: string;
  recommended_specialty_tr?: string;
  confidence_label_tr?: string;
  confidence_0_1?: number;
  stop_reason?: string;
};

type Props = {
  onBack: () => void;
  onViewSession?: (sessionId: string) => void;
};

/**
 * HistoryScreen — shows the user's past triage sessions.
 * Fetches from / triage_sessions using device_id for filtering.
 */
export default function HistoryScreen({ onBack, onViewSession }: Props) {
  const { t } = useI18n();
  const tokens = useTokens();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSessions = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE}/v1/triage/history?limit=50`,
        {
          headers: {
            "x-device-id": getDeviceId(),
          },
        }
      );

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setSessions(data.items ?? []);
    } catch (err: any) {
      setError(t("history.errorLoading"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const envelopeColor = useCallback(
    (type: string) => {
      switch (type) {
        case "EMERGENCY":
          return { bg: "#FFEBEE", text: tokens.colors.error };
        case "RESULT":
          return { bg: "#E8F5E9", text: tokens.colors.success };
        case "SAME_DAY":
          return { bg: "#FFF8E1", text: tokens.colors.warning };
        default:
          return {
            bg: tokens.colors.surfaceAlt,
            text: tokens.colors.textSecondary,
          };
      }
    },
    [tokens],
  );

  const styles = useMemo(
    () =>
      StyleSheet.create({
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
          width: 60,
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
        center: {
          flex: 1,
          justifyContent: "center",
          alignItems: "center",
          paddingHorizontal: screenPadding,
        },
        errorText: {
          ...tokens.typography.body,
          color: tokens.colors.error,
          textAlign: "center",
          marginBottom: tokens.spacing.lg,
        },
        emptyIcon: {
          fontSize: 48,
          marginBottom: tokens.spacing.md,
        },
        emptyTitle: {
          ...tokens.typography.h1,
          marginBottom: tokens.spacing.sm,
        },
        emptySubtitle: {
          textAlign: "center",
          paddingHorizontal: tokens.spacing.xl,
        },
        list: {
          padding: screenPadding,
          gap: tokens.spacing.md,
          paddingBottom: tokens.spacing.xxl,
        },
        sessionCard: {
          backgroundColor: tokens.colors.surface,
          borderRadius: tokens.radius.xl,
          borderWidth: 1,
          borderColor: tokens.colors.border,
          padding: tokens.spacing.lg,
          ...tokens.shadow.card,
        },
        sessionCardPressed: {
          opacity: 0.85,
          transform: [{ scale: 0.985 }],
        },
        sessionHeader: {
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: tokens.spacing.sm,
        },
        typeBadge: {
          paddingHorizontal: tokens.spacing.md,
          paddingVertical: tokens.spacing.xs,
          borderRadius: tokens.radius.sm,
        },
        typeBadgeText: {
          fontSize: 12,
          fontWeight: "700",
          letterSpacing: 0.5,
        },
        dateText: {
          fontSize: 12,
        },
        specialtyRow: {
          flexDirection: "row",
          alignItems: "center",
          marginBottom: tokens.spacing.sm,
          gap: tokens.spacing.xs,
        },
        specialtyIcon: {
          fontSize: 18,
        },
        specialtyText: {
          ...tokens.typography.body,
          fontWeight: "600",
          color: tokens.colors.textPrimary,
        },
        metaRow: {
          flexDirection: "row",
          flexWrap: "wrap",
          gap: tokens.spacing.xs,
        },
        metaChip: {
          backgroundColor: tokens.colors.surfaceAlt,
          paddingHorizontal: tokens.spacing.sm,
          paddingVertical: 3,
          borderRadius: tokens.radius.pill,
        },
        metaChipText: {
          ...tokens.typography.caption,
          fontWeight: "500",
        },
        footer: {
          textAlign: "center",
          paddingVertical: tokens.spacing.lg,
        },
        // Emergency-variant card. Stitch pattern: red left border + soft
        // red bg + "ACİL" pill + "X OLABİLİR." body + inline red 112'yi Ara
        // button. Distinct enough from the normal card that a user
        // glancing at History can spot the urgent rows without reading.
        emergencyCard: {
          borderRadius: tokens.radius.xl,
          borderWidth: 1,
          borderColor: tokens.colors.errorBorder,
          borderLeftWidth: 4,
          borderLeftColor: tokens.colors.error,
          backgroundColor: tokens.colors.errorBg,
          padding: tokens.spacing.lg,
          ...tokens.shadow.card,
        },
        emergencyTitleRow: {
          flexDirection: "row",
          alignItems: "center",
          gap: tokens.spacing.xs,
          marginBottom: tokens.spacing.xs,
        },
        emergencyIcon: {
          fontSize: 16,
          color: tokens.colors.error,
        },
        emergencyTitle: {
          ...tokens.typography.h2,
          color: tokens.colors.textPrimary,
          flex: 1,
        },
        emergencyChip: {
          backgroundColor: tokens.colors.error,
          paddingHorizontal: tokens.spacing.sm,
          paddingVertical: 3,
          borderRadius: tokens.radius.pill,
        },
        emergencyChipText: {
          fontSize: 11,
          fontWeight: "700",
          color: "#FFFFFF",
          letterSpacing: 0.6,
        },
        emergencyDate: {
          ...tokens.typography.caption,
          color: tokens.colors.textSecondary,
          marginBottom: tokens.spacing.sm,
        },
        emergencyDivider: {
          height: 1,
          backgroundColor: tokens.colors.errorDivider,
          marginVertical: tokens.spacing.sm,
        },
        emergencyOlabilir: {
          ...tokens.typography.body,
          fontWeight: "600",
          color: tokens.colors.textPrimary,
        },
        emergencyHint: {
          ...tokens.typography.bodySmall,
          color: tokens.colors.textSecondary,
          marginTop: 2,
          marginBottom: tokens.spacing.sm,
        },
        emergencyCallBtn: {
          minHeight: 40,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: tokens.spacing.xs,
          backgroundColor: tokens.colors.error,
          borderRadius: tokens.radius.pill,
          paddingHorizontal: tokens.spacing.lg,
          marginBottom: tokens.spacing.sm,
        },
        emergencyCallBtnText: {
          ...tokens.typography.button,
          color: "#FFFFFF",
        },
        emergencyMetaRow: {
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        },
        emergencyDetailLink: {
          ...tokens.typography.bodySmall,
          fontWeight: "600",
          color: tokens.colors.error,
        },
      }),
    [tokens],
  );

  const renderItem = ({ item }: { item: SessionItem }) => {
    const ec = envelopeColor(item.envelope_type);
    const date = new Date(item.created_at);
    const dateStr = date.toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
    const timeStr = date.toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
    });

    if (item.envelope_type === "EMERGENCY") {
      // Emergency variant matching the Stitch History card spec: red
      // border + "ACİL" chip + "X OLABİLİR." copy + inline 112'yi Ara
      // button. Backend doesn't surface an emergency-condition label
      // yet, so we use the recommended specialty (or a generic
      // fallback) before the OLABİLİR.; once the field exists we can
      // swap in the more specific phrasing without UI churn.
      const emergencyLabel =
        item.recommended_specialty_tr || t("history.emergencyFallback");
      return (
        <Pressable
          onPress={() => onViewSession?.(item.id)}
          accessibilityRole="button"
          accessibilityLabel={`${t("history.emergency")} oturumu, ${dateStr}`}
          style={({ pressed }) => [
            styles.emergencyCard,
            pressed && styles.sessionCardPressed,
          ]}
        >
          <View style={styles.emergencyTitleRow}>
            <Text style={styles.emergencyIcon}>⚠</Text>
            <Text style={styles.emergencyTitle}>
              {item.recommended_specialty_tr ||
                t("history.emergencyFallbackSpecialty")}
            </Text>
            <View style={styles.emergencyChip}>
              <Text style={styles.emergencyChipText}>
                {t("history.emergencyChip")}
              </Text>
            </View>
          </View>
          <Text style={styles.emergencyDate}>
            {dateStr} • {timeStr}
          </Text>
          <View style={styles.emergencyDivider} />
          <Text style={styles.emergencyOlabilir}>
            {t("history.emergencyOlabilir").replace(
              "{{label}}",
              emergencyLabel,
            )}
          </Text>
          <Text style={styles.emergencyHint}>
            {t("history.emergencyHint")}
          </Text>
          <Pressable
            onPress={(e) => {
              // Tapping the call button shouldn't also open the detail
              // view — stop the event from bubbling to the outer
              // Pressable. RN's stopPropagation on Pressable nestable
              // gestures is best-effort; this works in practice on
              // iOS / Android because the inner Pressable wins focus.
              e?.stopPropagation?.();
              Linking.openURL("tel:112").catch(() => {});
            }}
            accessibilityRole="button"
            accessibilityLabel={t("history.emergencyCall")}
            style={styles.emergencyCallBtn}
          >
            <Text style={styles.emergencyCallBtnText}>
              📞  {t("history.emergencyCall")}
            </Text>
          </Pressable>
          <View style={styles.emergencyMetaRow}>
            {item.stop_reason ? (
              <Text style={styles.metaChipText}>
                {item.stop_reason.replace(/_/g, " ")}
              </Text>
            ) : (
              <View />
            )}
            <Text style={styles.emergencyDetailLink}>
              {t("history.detailCta")} →
            </Text>
          </View>
        </Pressable>
      );
    }

    return (
      <Pressable
        style={({ pressed }) => [
          styles.sessionCard,
          pressed && styles.sessionCardPressed,
        ]}
        onPress={() => onViewSession?.(item.id)}
        accessibilityRole="button"
        accessibilityLabel={`${item.envelope_type} oturumu, ${dateStr}`}
      >
        <View style={styles.sessionHeader}>
          <View style={[styles.typeBadge, { backgroundColor: ec.bg }]}>
            <Text style={[styles.typeBadgeText, { color: ec.text }]}>
              {item.envelope_type === "EMERGENCY"
                ? t("history.emergency")
                : item.envelope_type === "RESULT"
                  ? t("history.result")
                  : item.envelope_type === "SAME_DAY"
                    ? t("history.sameDay")
                    : item.envelope_type}
            </Text>
          </View>
          <MutedText style={styles.dateText}>
            {dateStr} • {timeStr}
          </MutedText>
        </View>

        {item.recommended_specialty_tr && (
          <View style={styles.specialtyRow}>
            <Text style={styles.specialtyIcon}>🩺</Text>
            <Text style={styles.specialtyText}>
              {item.recommended_specialty_tr}
            </Text>
          </View>
        )}

        <View style={styles.metaRow}>
          {item.confidence_label_tr && (
            <View style={styles.metaChip}>
              <Text style={styles.metaChipText}>
                {t("history.confidence")}: {item.confidence_label_tr}
                {typeof item.confidence_0_1 === "number"
                  ? ` (${Math.round(item.confidence_0_1 * 100)}%)`
                  : ""}
              </Text>
            </View>
          )}
          {item.stop_reason && (
            <View style={styles.metaChip}>
              <Text style={styles.metaChipText}>
                {item.stop_reason.replace(/_/g, " ")}
              </Text>
            </View>
          )}
        </View>
      </Pressable>
    );
  };

  return (
    <ScreenContainer style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backText}>{t("history.back")}</Text>
        </Pressable>
        <Text style={styles.title}>{t("history.title")}</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Content */}
      {loading && !refreshing ? (
        // Phase B6: Skeleton placeholders match the session-card
        // shape so the transition to real data is seamless. Screen
        // readers get the "history.loading" text still; skeletons
        // themselves are marked accessibilityElementsHidden.
        <View style={styles.list}>
          <MutedText
            style={{ marginBottom: tokens.spacing.md, textAlign: "center" }}
          >
            {t("history.loading")}
          </MutedText>
          <SkeletonList count={4} Item={SessionCardSkeleton} />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <SecondaryButton onPress={() => fetchSessions()}>
            {t("common.retry")}
          </SecondaryButton>
        </View>
      ) : sessions.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyIcon}>📋</Text>
          <Text style={styles.emptyTitle}>{t("history.empty")}</Text>
          <MutedText style={styles.emptySubtitle}>
            {t("history.emptySubtitle")}
          </MutedText>
          <PrimaryButton
            onPress={onBack}
            style={{ marginTop: tokens.spacing.lg }}
          >
            {t("history.startNew")}
          </PrimaryButton>
        </View>
      ) : (
        <FlatList
          data={sessions}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchSessions(true)}
              tintColor={tokens.colors.primary}
            />
          }
          ListFooterComponent={
            <MutedText style={styles.footer}>
              {t("history.showingCount").replace(
                "{{count}}",
                String(sessions.length),
              )}
            </MutedText>
          }
        />
      )}
    </ScreenContainer>
  );
}
