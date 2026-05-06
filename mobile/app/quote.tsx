/**
 * /quote — health-tourism flow entry route.
 *
 * Uses expo-router's stack so the user can hit the back button to
 * return to the triage entry. The dispatcher inside HtFlowScreen
 * decides which step screen to render based on `quoteStore.step`.
 */
import React from "react";
import { SafeAreaView, StyleSheet } from "react-native";
import HtFlowScreen from "@/src/screens/quote/HtFlowScreen";
import { tokens } from "@/src/ui/designTokens";

export default function QuoteRoute() {
  return (
    <SafeAreaView style={styles.safe}>
      <HtFlowScreen />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: tokens.colors.background,
  },
});
