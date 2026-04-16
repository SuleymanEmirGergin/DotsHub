/**
 * React Error Boundary: render sırasında fırlayan hataları yakalar,
 * fallback UI gösterir ve "Yeniden dene" ile çocukları yeniden mount eder.
 */

import React, { type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { getText, getLocale } from "@/i18n/index";
import { tokens } from "@/src/ui/designTokens";

type Props = {
  children: ReactNode;
  /** Retry tıklanınca çağrılır; key artırılarak çocuklar yeniden mount edilir. */
  onRetry: () => void;
};

type State = {
  error: Error | null;
  retryKey: number;
};

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, retryKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // İsteğe bağlı: log / raporlama
    if (__DEV__) {
      console.warn("ErrorBoundary caught:", error?.message, errorInfo?.componentStack);
    }
  }

  handleRetry = (): void => {
    this.setState((prev) => ({ error: null, retryKey: prev.retryKey + 1 }));
    this.props.onRetry();
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <View style={styles.container}>
          <View style={styles.card}>
            <Text style={styles.title}>{getText(getLocale(), "error.title")}</Text>
            <Text style={styles.message}>{getText(getLocale(), "error.fallbackMessage")}</Text>
            <Pressable style={styles.button} onPress={this.handleRetry}>
              <Text style={styles.buttonText}>{getText(getLocale(), "common.retry")}</Text>
            </Pressable>
          </View>
        </View>
      );
    }
    return <React.Fragment key={this.state.retryKey}>{this.props.children}</React.Fragment>;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.background,
  },
  card: {
    backgroundColor: tokens.colors.surface,
    borderRadius: tokens.radius.lg,
    padding: tokens.spacing.xl,
    maxWidth: 320,
    alignItems: "center",
  },
  title: {
    ...tokens.typography.title,
    marginBottom: tokens.spacing.sm,
  },
  message: {
    ...tokens.typography.body,
    color: tokens.colors.textSecondary,
    textAlign: "center",
    marginBottom: tokens.spacing.lg,
  },
  button: {
    backgroundColor: tokens.colors.primary,
    paddingHorizontal: tokens.spacing.lg,
    paddingVertical: tokens.spacing.sm,
    borderRadius: tokens.radius.md,
  },
  buttonText: {
    ...tokens.typography.button,
    color: "#FFFFFF",
  },
});
