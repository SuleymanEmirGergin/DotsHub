/**
 * Animated skeleton placeholders for loading states.
 *
 * Why not ActivityIndicator: a spinner tells the user "we're busy"
 * but not "what you'll see next". A skeleton that matches the shape
 * of the upcoming content (e.g. session card, result row) gives
 * faster visual commitment — the layout doesn't jump when data lands.
 *
 * Implementation: pulsing opacity (0.3 → 1.0 → 0.3 loop) via
 * `Animated.Value`. Deliberately avoids `expo-linear-gradient` (a
 * shimmering horizontal sweep is prettier but adds a native module
 * dependency; opacity pulse is native-driver-safe and zero-dep).
 *
 * Usage:
 *
 *   <SkeletonBlock width={80} height={16} />          // inline
 *   <SessionCardSkeleton />                            // pre-shaped
 *   <SkeletonList count={5} Item={SessionCardSkeleton} />
 */

import React, { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import type { ViewStyle } from "react-native";
import { tokens } from "@/src/ui/designTokens";

export type SkeletonBlockProps = {
  width?: number | string;
  height?: number;
  style?: ViewStyle;
  /**
   * Unique "phase offset" in ms to stagger pulse between adjacent
   * skeleton blocks. Without it, 10 skeletons on screen all pulse in
   * lockstep — looks mechanical. Default: 0 (no offset).
   */
  delay?: number;
};

export function SkeletonBlock({
  width = "100%",
  height = 16,
  style,
  delay = 0,
}: SkeletonBlockProps) {
  const opacity = useRef(new Animated.Value(0.3)).current;

  useEffect(() => {
    // Sequence: fade up → fade down → repeat. `useNativeDriver: true`
    // keeps the animation off the JS thread (smoother on low-end
    // Android). Start after `delay` so multi-block layouts shimmer
    // in a wave rather than all at once.
    const sequence = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 800,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.3,
          duration: 800,
          useNativeDriver: true,
        }),
      ])
    );
    const startTimer = setTimeout(() => sequence.start(), delay);
    return () => {
      clearTimeout(startTimer);
      sequence.stop();
    };
  }, [opacity, delay]);

  return (
    <Animated.View
      style={[
        styles.block,
        {
          width: width as ViewStyle["width"],
          height,
          opacity,
        },
        style,
      ]}
      // Screen readers should not announce skeletons — they're
      // decorative; the actual content replaces them shortly after.
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}

/**
 * Session card-shaped skeleton — matches HistoryScreen's sessionCard
 * layout so the handoff from loading→loaded feels continuous.
 * Two block rows (header badge + date, specialty line) with stacked
 * padding matching the real card.
 */
export function SessionCardSkeleton({ delay = 0 }: { delay?: number }) {
  return (
    <View style={styles.sessionCard} accessibilityElementsHidden>
      <View style={styles.sessionHeader}>
        <SkeletonBlock width={72} height={22} delay={delay} />
        <SkeletonBlock width={110} height={14} delay={delay + 60} />
      </View>
      <SkeletonBlock width="60%" height={18} delay={delay + 120} />
      <View style={styles.metaRow}>
        <SkeletonBlock width={90} height={14} delay={delay + 180} />
        <SkeletonBlock width={70} height={14} delay={delay + 240} />
      </View>
    </View>
  );
}

/**
 * Result-ish card skeleton — bigger title row + multiline body.
 * Used by ResultScreen while routing/candidates are loading.
 */
export function ResultCardSkeleton() {
  return (
    <View style={styles.resultCard} accessibilityElementsHidden>
      <SkeletonBlock width="50%" height={22} />
      <SkeletonBlock width="80%" height={16} style={{ marginTop: tokens.spacing.md }} delay={100} />
      <SkeletonBlock width="70%" height={16} style={{ marginTop: tokens.spacing.xs }} delay={160} />
      <SkeletonBlock width="90%" height={16} style={{ marginTop: tokens.spacing.xs }} delay={220} />
    </View>
  );
}

/**
 * Render N skeletons of a given component. Shorthand for list/feed
 * placeholders — `<SkeletonList count={5} Item={SessionCardSkeleton}/>`.
 */
export function SkeletonList({
  count,
  Item,
}: {
  count: number;
  Item: React.ComponentType<{ delay?: number }>;
}) {
  return (
    <View style={styles.list}>
      {Array.from({ length: count }).map((_, i) => (
        <Item key={i} delay={i * 80} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    backgroundColor: tokens.colors.surfaceAlt,
    borderRadius: tokens.radius.sm,
  },
  list: {
    gap: tokens.spacing.md,
  },
  sessionCard: {
    backgroundColor: tokens.colors.surface,
    borderRadius: tokens.radius.xl,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    padding: tokens.spacing.lg,
    gap: tokens.spacing.sm,
  },
  sessionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metaRow: {
    flexDirection: "row",
    gap: tokens.spacing.xs,
    marginTop: tokens.spacing.xs,
  },
  resultCard: {
    backgroundColor: tokens.colors.surface,
    borderRadius: tokens.radius.xl,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    padding: tokens.spacing.xl,
    gap: tokens.spacing.xs,
  },
});
