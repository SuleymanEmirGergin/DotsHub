import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';

interface RiskBadgeProps {
  level: string;
  size?: 'sm' | 'md';
}

const riskConfig: Record<string, { color: string; label: string }> = {
  LOW: { color: Colors.riskLow, label: 'Düşük Risk' },
  MEDIUM: { color: Colors.riskMedium, label: 'Orta Risk' },
  HIGH: { color: Colors.riskHigh, label: 'Yüksek Risk' },
};

export default function RiskBadge({ level, size = 'md' }: RiskBadgeProps) {
  const config = riskConfig[level] || riskConfig.LOW;
  const isSm = size === 'sm';

  return (
    <View style={[styles.badge, { backgroundColor: config.color + '20' }, isSm && styles.badgeSm]}>
      <View style={[styles.dot, { backgroundColor: config.color }]} />
      <Text style={[styles.text, { color: config.color }, isSm && styles.textSm]}>
        {config.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    alignSelf: 'flex-start',
  },
  badgeSm: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: Spacing.sm,
  },
  text: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  textSm: {
    fontSize: FontSizes.xs,
  },
});
