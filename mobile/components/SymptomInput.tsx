import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';

export default function DisclaimerBanner() {
  return (
    <View style={styles.banner}>
      <Text style={styles.icon}>ℹ️</Text>
      <Text style={styles.text}>
        Bu uygulama tanı koymaz. Bilgilendirme ve yönlendirme amaçlıdır. Her zaman bir sağlık
        profesyoneline danışın.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    backgroundColor: Colors.disclaimer,
    borderWidth: 1,
    borderColor: Colors.disclaimerBorder,
    borderRadius: BorderRadius.sm,
    padding: Spacing.sm + 2,
    marginHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    alignItems: 'flex-start',
  },
  icon: {
    fontSize: 16,
    marginRight: Spacing.sm,
    marginTop: 1,
  },
  text: {
    flex: 1,
    fontSize: FontSizes.xs,
    color: Colors.disclaimerText,
    lineHeight: 18,
  },
});
