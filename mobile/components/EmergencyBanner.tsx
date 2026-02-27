import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';

interface EmergencyBannerProps {
  instructions: string[];
  reason?: string;
}

export default function EmergencyBanner({ instructions, reason }: EmergencyBannerProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>🚨</Text>
      <Text style={styles.title}>ACİL DURUM UYARISI</Text>
      {reason ? <Text style={styles.reason}>{reason}</Text> : null}
      {instructions.map((instruction, index) => (
        <Text key={index} style={styles.instruction}>
          • {instruction}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.emergency,
    borderWidth: 2,
    borderColor: Colors.emergencyBorder,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.sm,
    alignItems: 'center',
  },
  icon: {
    fontSize: 32,
    marginBottom: Spacing.sm,
  },
  title: {
    fontSize: FontSizes.lg,
    fontWeight: '800',
    color: Colors.emergencyText,
    marginBottom: Spacing.sm,
  },
  reason: {
    fontSize: FontSizes.sm,
    color: Colors.emergencyText,
    marginBottom: Spacing.sm,
    textAlign: 'center',
  },
  instruction: {
    fontSize: FontSizes.md,
    color: Colors.emergencyText,
    marginBottom: Spacing.xs,
    alignSelf: 'flex-start',
    fontWeight: '600',
  },
});
