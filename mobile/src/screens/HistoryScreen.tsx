import React, { useEffect, useState, useCallback } from "react";
import {
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
  RefreshControl,
} from "react-native";
import { tokens, screenPadding } from "@/src/ui/designTokens";
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
import { getCachedResults } from "@/src/state/offlineCache";

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
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // When true the list is being served from the AsyncStorage fallback,
  // not the backend. Shown as a subtle banner so the user understands
  // why the list might be shorter than normal and isn't auto-updating.
  const [fromCache, setFromCache] = useState(false);

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
      setFromCache(false);
    } catch (err: any) {
      // Backend unreachable → try the offline cache. We only surface
      // the hard error state if we have literally nothing to show.
      const cached = await getCachedResults();
      if (cached.length > 0) {
        setSessions(cached as SessionItem[]);
        setFromCache(true);
        setError(null);
      } else {
        setError(t("history.errorLoading"));
        setFromCache(false);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [t]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const envelopeColor = (type: string) => {
    switch (type) {
      case "EMERGENCY":
        return { bg: "#FFEBEE", text: tokens.colors.error };
      case "RESULT":
        return { bg: "#E8F5E9", text: tokens.colors.success };
      case "SAME_DAY":
        return { bg: "#FFF8E1", text: tokens.colors.warning };
      default:
        return { bg: tokens.colors.surfaceAlt, text: tokens.colors.textSecondary };
    }
  };

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
          <View
            style={[
              styles.typeBadge,
              { backgroundColor: ec.bg },
            ]}
          >
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

      {/* Offline banner — only when we're serving cached data. */}
      {fromCache && !loading && !refreshing ? (
        <View style={styles.offlineBanner} accessibilityRole="alert">
          <Text style={styles.offlineIcon}>📡</Text>
          <Text style={styles.offlineText}>
            {t("history.offlineCacheNotice")}
          </Text>
        </View>
      ) : null}

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
          <PrimaryButton onPress={onBack} style={{ marginTop: tokens.spacing.lg }}>
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
              {t("history.showingCount").replace("{{count}}", String(sessions.length))}
            </MutedText>
          }
        />
      )}
    </ScreenContainer>
  );
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
  offlineBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: tokens.spacing.sm,
    paddingHorizontal: screenPadding,
    paddingVertical: tokens.spacing.sm,
    backgroundColor: "#FFF8E1",
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
  },
  offlineIcon: {
    fontSize: 16,
  },
  offlineText: {
    ...tokens.typography.caption,
    color: tokens.colors.textSecondary,
    flex: 1,
    fontWeight: "500",
  },
});
