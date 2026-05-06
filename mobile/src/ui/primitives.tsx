import React, { useMemo, type ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { screenPadding, touchTargetMin } from "@/src/ui/designTokens";
import { useTokens } from "@/src/ui/useTokens";

// Shared visual primitives. Every component here subscribes to
// `useTokens()` so flipping the theme in Settings (Modern Friendly ↔
// Sade Medikal) re-paints the surfaces, cards, badges, dividers and
// buttons used across every screen — no per-screen migration required.
//
// Style objects are built inside the component body (via useMemo so we
// don't allocate a new object on every render) rather than at module
// scope. That's the only way to react to theme changes without
// remounting the tree.

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
  // "link" is allowed for buttons that visually look like buttons but
  // navigate to an external surface (e.g. ResultScreen's "open in maps"
  // CTA). Screen readers announce links differently from buttons —
  // surfacing the right semantic helps blind users predict the
  // destination behavior.
  accessibilityRole?: "button" | "link";
  accessibilityLabel?: string;
  accessibilityState?: { disabled?: boolean; selected?: boolean };
};

export function ScreenContainer({ children, style }: CommonProps) {
  const t = useTokens();
  const containerStyle = useMemo<ViewStyle>(
    () => ({
      flex: 1,
      backgroundColor: t.colors.background,
      paddingHorizontal: screenPadding,
    }),
    [t],
  );
  return <View style={[containerStyle, style]}>{children}</View>;
}

export function Card({ children, style }: CommonProps) {
  const t = useTokens();
  const cardStyle = useMemo<ViewStyle>(
    () => ({
      backgroundColor: t.colors.surface,
      borderRadius: t.radius.xl,
      borderWidth: 1,
      borderColor: t.colors.border,
      padding: t.spacing.xl,
      ...t.shadow.card,
    }),
    [t],
  );
  return <View style={[cardStyle, style]}>{children}</View>;
}

export function SectionTitle({ children, style }: TextCommonProps) {
  const t = useTokens();
  const sectionStyle = useMemo<TextStyle>(
    () => ({
      ...t.typography.h2,
      color: t.colors.textPrimary,
      marginBottom: t.spacing.md,
    }),
    [t],
  );
  return <Text style={[sectionStyle, style]}>{children}</Text>;
}

export function MutedText({ children, style }: TextCommonProps) {
  const t = useTokens();
  const mutedStyle = useMemo<TextStyle>(
    () => ({
      ...t.typography.caption,
      color: t.colors.textMuted,
    }),
    [t],
  );
  return <Text style={[mutedStyle, style]}>{children}</Text>;
}

export function Divider({ style }: { style?: StyleProp<ViewStyle> }) {
  const t = useTokens();
  const dividerStyle = useMemo<ViewStyle>(
    () => ({
      height: 1,
      backgroundColor: t.colors.border,
      marginVertical: t.spacing.lg,
    }),
    [t],
  );
  return <View style={[dividerStyle, style]} />;
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
  const t = useTokens();
  const { container, text } = useMemo(
    () => ({
      container: {
        alignSelf: "flex-start",
        borderRadius: t.radius.pill,
        backgroundColor: t.colors.surfaceAlt,
        paddingHorizontal: t.spacing.md,
        paddingVertical: t.spacing.xs,
      } as ViewStyle,
      text: {
        ...t.typography.caption,
        color: t.colors.textSecondary,
        fontWeight: "600" as const,
      } as TextStyle,
    }),
    [t],
  );
  return (
    <View style={[container, style]}>
      <Text style={[text, textStyle]}>{children}</Text>
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
  accessibilityRole,
  accessibilityLabel,
  accessibilityState,
}: ButtonProps & { variant: "primary" | "secondary" | "danger" }) {
  const t = useTokens();
  const variantStyle = t.button[variant];

  const baseStyle = useMemo<ViewStyle>(
    () => ({
      minHeight: touchTargetMin,
      borderRadius: t.radius.md,
      borderWidth: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: t.spacing.lg,
      paddingVertical: t.spacing.sm,
    }),
    [t],
  );
  const textBaseStyle = useMemo<TextStyle>(
    () => ({ ...t.typography.button }),
    [t],
  );

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      // Default to "button" so screen-readers announce the element as
      // pressable. Callers can opt into "link" for buttons that hand
      // off to an external surface (maps, store listing, etc.).
      accessibilityRole={accessibilityRole ?? "button"}
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{
        disabled: !!disabled,
        ...(accessibilityState ?? {}),
      }}
      style={({ pressed }) => [
        baseStyle,
        variantStyle.container,
        pressed && !disabled ? STATIC.buttonPressed : null,
        disabled ? STATIC.buttonDisabled : null,
        style,
      ]}
    >
      <Text style={[textBaseStyle, variantStyle.text, textStyle]}>
        {children}
      </Text>
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

// Theme-independent style scraps live in StyleSheet so RN can hand them
// to the native side as registered IDs. (Anything that depends on the
// active palette must instead be built per-render with useMemo.)
const STATIC = StyleSheet.create({
  buttonPressed: {
    opacity: 0.9,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
});
