import type { TextStyle, ViewStyle } from "react-native";

// ──────────────────────────────────────────────────────────────────────────
// Theme system
//
// Two palettes ship with the app:
//
//   - "modern" (Modern Friendly, default): warm cream surface + teal accent.
//     The Stitch design system's primary direction — friendly hospital app
//     vs. classic clinical. Backed by Manrope + Plus Jakarta in higher-
//     fidelity builds; falls back to system fonts here since we have no
//     custom font loader yet.
//   - "sade"   (Sade Medikal): cool slate surface + medical blue accent.
//     Pre-2026-05 baseline used across IntroScreen / Result / Emergency.
//     Kept as opt-in for users who want the classic clinical look.
//
// The two palettes share the same shape (`Tokens`) so any code that
// consumes `tokens.colors.x` will keep working under either palette.
// Components that want to react to theme changes should call
// `useTokens()` (see ./useTokens.ts) — the static `tokens` export below
// resolves to whichever palette is active *at module load time* and is
// fine for screens that don't need live re-theming yet.
// ──────────────────────────────────────────────────────────────────────────

type ButtonVariant = {
  container: ViewStyle;
  text: TextStyle;
};

export type ThemeName = "modern" | "sade";

export type Tokens = {
  colors: {
    background: string;
    surface: string;
    surfaceAlt: string;
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    primary: string;
    primaryPressed: string;
    /** Accent colour: teal on modern, medical blue on sade. Used for
     *  highlights, links, focus rings, confidence chip text. */
    accent: string;
    /** Soft accent surface — chip backgrounds, info pills. */
    accentSoft: string;
    /** Text colour for content laid on top of accentSoft. */
    accentSoftText: string;
    border: string;
    success: string;
    warning: string;
    error: string;
    errorBg: string;
    errorBorder: string;
    errorDivider: string;
    infoBg: string;
    infoBorder: string;
    infoText: string;
  };
  spacing: {
    xs: number;
    sm: number;
    md: number;
    lg: number;
    xl: number;
    xxl: number;
  };
  radius: {
    sm: number;
    md: number;
    lg: number;
    xl: number;
    pill: number;
  };
  typography: {
    title: TextStyle;
    h1: TextStyle;
    h2: TextStyle;
    body: TextStyle;
    bodySmall: TextStyle;
    caption: TextStyle;
    button: TextStyle;
  };
  shadow: {
    card: ViewStyle;
    soft: ViewStyle;
    focus: ViewStyle;
  };
  button: {
    primary: ButtonVariant;
    secondary: ButtonVariant;
    danger: ButtonVariant;
    ghost: ButtonVariant;
  };
};

// Spacing / radius / typography / shadow are shared across themes — the
// difference between Modern Friendly and Sade Medikal is purely chromatic.
// Hoist the shared parts into one constant so they don't drift.
const SHARED_NON_COLOR = {
  spacing: {
    xs: 6,
    sm: 10,
    md: 14,
    lg: 18,
    xl: 24,
    xxl: 32,
  },
  radius: {
    sm: 10,
    md: 14,
    lg: 18,
    xl: 22,
    pill: 999,
  },
  typography: {
    title: { fontSize: 28, lineHeight: 34, fontWeight: "700" as const },
    h1: { fontSize: 22, lineHeight: 30, fontWeight: "700" as const },
    h2: { fontSize: 17, lineHeight: 24, fontWeight: "600" as const },
    body: { fontSize: 15, lineHeight: 22, fontWeight: "400" as const },
    bodySmall: { fontSize: 14, lineHeight: 20, fontWeight: "400" as const },
    caption: { fontSize: 12, lineHeight: 17, fontWeight: "400" as const },
    button: { fontSize: 16, lineHeight: 22, fontWeight: "600" as const },
  },
  shadow: {
    card: {
      shadowColor: "#0F172A",
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.08,
      shadowRadius: 12,
      elevation: 3,
    },
    soft: {
      shadowColor: "#0F172A",
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.05,
      shadowRadius: 8,
      elevation: 1,
    },
    focus: {
      shadowColor: "#2563EB",
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0.2,
      shadowRadius: 8,
      elevation: 0,
    },
  },
};

// Per-theme font families. The string values must match what
// `useFonts()` registers in `app/_layout.tsx` — typoing the family
// name will silently fall back to the system font.
//
// Modern Friendly pairs Manrope (headline) + Plus Jakarta Sans (body)
// for warmth + readability. Sade Medikal uses Inter throughout for the
// classic clinical look. Fonts are bundled lazy by @expo-google-fonts
// so we only ship the four weights actually referenced here.
type FontConfig = {
  headline: string;
  body: string;
};

const MODERN_FONTS: FontConfig = {
  headline: "Manrope_700Bold",
  body: "PlusJakartaSans_400Regular",
};

const SADE_FONTS: FontConfig = {
  headline: "Inter_700Bold",
  body: "Inter_400Regular",
};

function buildPalette(c: Tokens["colors"], fonts: FontConfig): Tokens {
  // Typography colour AND fontFamily bake into the text style so legacy
  // spreads like `...tokens.typography.title` keep producing a complete
  // style — every screen that imports the typography spreads gets the
  // theme's fontFamily for free.
  const typography: Tokens["typography"] = {
    title: {
      ...SHARED_NON_COLOR.typography.title,
      color: c.textPrimary,
      fontFamily: fonts.headline,
    },
    h1: {
      ...SHARED_NON_COLOR.typography.h1,
      color: c.textPrimary,
      fontFamily: fonts.headline,
    },
    h2: {
      ...SHARED_NON_COLOR.typography.h2,
      color: c.textPrimary,
      fontFamily: fonts.headline,
    },
    body: {
      ...SHARED_NON_COLOR.typography.body,
      color: c.textSecondary,
      fontFamily: fonts.body,
    },
    bodySmall: {
      ...SHARED_NON_COLOR.typography.bodySmall,
      color: c.textSecondary,
      fontFamily: fonts.body,
    },
    caption: {
      ...SHARED_NON_COLOR.typography.caption,
      color: c.textMuted,
      fontFamily: fonts.body,
    },
    button: {
      ...SHARED_NON_COLOR.typography.button,
      color: "#FFFFFF",
      fontFamily: fonts.body,
    },
  };

  const button: Tokens["button"] = {
    primary: {
      container: { backgroundColor: c.primary, borderColor: c.primary },
      text: { color: "#FFFFFF" },
    },
    secondary: {
      container: { backgroundColor: c.surface, borderColor: c.border },
      text: { color: c.textPrimary },
    },
    danger: {
      container: { backgroundColor: c.error, borderColor: c.error },
      text: { color: "#FFFFFF" },
    },
    ghost: {
      container: {
        backgroundColor: "transparent",
        borderColor: "transparent",
      },
      text: { color: c.textSecondary },
    },
  };

  return {
    colors: c,
    spacing: SHARED_NON_COLOR.spacing,
    radius: SHARED_NON_COLOR.radius,
    typography,
    shadow: SHARED_NON_COLOR.shadow,
    button,
  };
}

const MODERN_COLORS: Tokens["colors"] = {
  // Surface
  background: "#FDFAF6", // warm cream
  surface: "#FFFFFF",
  surfaceAlt: "#F5F1EA", // warm 100
  // Text
  textPrimary: "#0F172A",
  textSecondary: "#475569",
  textMuted: "#78716C", // warm muted
  // Brand / accent (teal — modern medical)
  primary: "#0F172A", // dark CTA stays slate (matches Stitch spec)
  primaryPressed: "#1E293B",
  accent: "#14B8A6", // teal
  accentSoft: "#CCFBF1", // teal-50
  accentSoftText: "#115E59", // teal-800
  // Borders
  border: "#E7E2DA", // warm border
  // Status
  success: "#15803D",
  warning: "#D97706",
  error: "#B91C1C",
  errorBg: "#FEF2F2",
  errorBorder: "#FCA5A5",
  errorDivider: "#FBD5D5",
  infoBg: "#CCFBF1", // re-uses accentSoft so info badges look on-brand
  infoBorder: "#99F6E4",
  infoText: "#115E59",
};

const SADE_COLORS: Tokens["colors"] = {
  // Surface
  background: "#F5F7FB", // cool neutral
  surface: "#FFFFFF",
  surfaceAlt: "#EEF2F7",
  // Text
  textPrimary: "#0F172A",
  textSecondary: "#334155",
  textMuted: "#64748B",
  // Brand / accent (medical blue)
  primary: "#0F172A",
  primaryPressed: "#1E293B",
  accent: "#2563EB", // medical blue
  accentSoft: "#EEF4FF",
  accentSoftText: "#1E3A8A",
  // Borders
  border: "#D7DEE8",
  // Status
  success: "#2E7D32",
  warning: "#F59E0B",
  error: "#C62828",
  errorBg: "#FFF8F8",
  errorBorder: "#F1B5B5",
  errorDivider: "#F2D4D4",
  infoBg: "#E8EEF8",
  infoBorder: "#D7E2F3",
  infoText: "#2F4F8F",
};

export const palettes: Record<ThemeName, Tokens> = {
  modern: buildPalette(MODERN_COLORS, MODERN_FONTS),
  sade: buildPalette(SADE_COLORS, SADE_FONTS),
};

/**
 * Default theme — Modern Friendly. Components that import `tokens`
 * directly will resolve to this palette and will not react to theme
 * switches at runtime. Components that need live theming should consume
 * `useTokens()` from `./useTokens.ts` instead.
 */
export const tokens: Tokens = palettes.modern;

export const screenPadding = palettes.modern.spacing.xl;
export const touchTargetMin = 44;
export const inputHeights = {
  sm: 40,
  md: 48,
  lg: 56,
} as const;
