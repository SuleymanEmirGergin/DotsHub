import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTriageStore } from "@/src/state/triageStore";
import { tokens } from "@/src/ui/designTokens";
import { Card, PrimaryButton, ScreenContainer, SectionTitle } from "@/src/ui/primitives";

export default function ErrorScreen() {
  const error = useTriageStore((s) => s.error);
  const resetSession = useTriageStore((s) => s.resetSession);

  return (
    <ScreenContainer style={styles.container}>
      <View style={styles.centerWrap}>
        <Card style={styles.card}>
          <Text style={styles.icon}>!</Text>
          <SectionTitle style={styles.title}>Bir sorun oldu</SectionTitle>
          <Text style={styles.message}>
            {error?.message_tr || "Beklenmeyen bir hata oluştu."}
          </Text>
          {error?.code ? <Text style={styles.code}>Kod: {error.code}</Text> : null}
        </Card>

        <PrimaryButton style={styles.retryButton} onPress={resetSession}>
          Yeni Oturum Başlat
        </PrimaryButton>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
  },
  centerWrap: {
    flex: 1,
    justifyContent: "center",
  },
  card: {
    alignItems: "center",
  },
  icon: {
    width: 62,
    height: 62,
    borderRadius: 31,
    textAlign: "center",
    lineHeight: 62,
    fontSize: 36,
    fontWeight: "700",
    color: tokens.colors.warning,
    backgroundColor: "#FEF3D2",
    marginBottom: tokens.spacing.md,
    overflow: "hidden",
  },
  title: {
    marginBottom: tokens.spacing.xs,
    textAlign: "center",
  },
  message: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    textAlign: "center",
    marginBottom: tokens.spacing.sm,
  },
  code: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
    fontFamily: "monospace",
  },
  retryButton: {
    marginTop: tokens.spacing.md,
  },
});
