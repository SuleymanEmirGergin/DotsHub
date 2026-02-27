import React, { type ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { screenPadding, tokens, touchTargetMin } from "@/src/ui/designTokens";

type CommonProps = {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
};

type TextCommonProps = {
  children: ReactNode;
  style?: StyleProp<TextStyle>;
};

type ButtonProps = {
  children: ReactNode;
  onPress?: () => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
};

export function ScreenContainer({ children, style }: CommonProps) {
  return <View style={[styles.screenContainer, style]}>{children}</View>;
}

export function Card({ children, style }: CommonProps) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children, style }: TextCommonProps) {
  return <Text style={[styles.sectionTitle, style]}>{children}</Text>;
}

export function MutedText({ children, style }: TextCommonProps) {
  return <Text style={[styles.mutedText, style]}>{children}</Text>;
}

export function Divider({ style }: { style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.divider, style]} />;
}

export function Badge({
  children,
  style,
  textStyle,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}) {
  return (
    <View style={[styles.badge, style]}>
      <Text style={[styles.badgeText, textStyle]}>{children}</Text>
    </View>
  );
}

function BaseButton({
  children,
  onPress,
  disabled,
  style,
  textStyle,
  variant,
}: ButtonProps & { variant: "primary" | "secondary" | "danger" }) {
  const variantStyle = tokens.button[variant];

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.buttonBase,
        variantStyle.container,
        pressed && !disabled ? styles.buttonPressed : null,
        disabled ? styles.buttonDisabled : null,
        style,
      ]}
    >
      <Text style={[styles.buttonText, variantStyle.text, textStyle]}>{children}</Text>
    </Pressable>
  );
}

export function PrimaryButton(props: ButtonProps) {
  return <BaseButton {...props} variant="primary" />;
}

export function SecondaryButton(props: ButtonProps) {
  return <BaseButton {...props} variant="secondary" />;
}

export function DangerButton(props: ButtonProps) {
  return <BaseButton {...props} variant="danger" />;
}

const styles = StyleSheet.create({
  screenContainer: {
    flex: 1,
    backgroundColor: tokens.colors.background,
    paddingHorizontal: screenPadding,
  },
  card: {
    backgroundColor: tokens.colors.surface,
    borderRadius: tokens.radius.xl,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    padding: tokens.spacing.xl,
    ...tokens.shadow.card,
  },
  sectionTitle: {
    ...tokens.typography.h2,
    color: tokens.colors.textPrimary,
    marginBottom: tokens.spacing.md,
  },
  mutedText: {
    ...tokens.typography.caption,
    color: tokens.colors.textMuted,
  },
  divider: {
    height: 1,
    backgroundColor: tokens.colors.border,
    marginVertical: tokens.spacing.lg,
  },
  badge: {
    alignSelf: "flex-start",
    borderRadius: tokens.radius.pill,
    backgroundColor: tokens.colors.surfaceAlt,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.xs,
  },
  badgeText: {
    ...tokens.typography.caption,
    color: tokens.colors.textSecondary,
    fontWeight: "600",
  },
  buttonBase: {
    minHeight: touchTargetMin,
    borderRadius: tokens.radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.lg,
    paddingVertical: tokens.spacing.sm,
  },
  buttonText: {
    ...tokens.typography.button,
  },
  buttonPressed: {
    opacity: 0.9,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
});
