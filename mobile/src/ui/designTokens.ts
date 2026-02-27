import type { TextStyle, ViewStyle } from "react-native";

type ButtonVariant = {
  container: ViewStyle;
  text: TextStyle;
};

export const tokens: {
  colors: {
    background: string;
    surface: string;
    surfaceAlt: string;
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    primary: string;
    primaryPressed: string;
    border: string;
    success: string;
    warning: string;
    error: string;
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
} = {
  colors: {
    background: "#F5F7FB",
    surface: "#FFFFFF",
    surfaceAlt: "#EEF2F7",
    textPrimary: "#0F172A",
    textSecondary: "#334155",
    textMuted: "#64748B",
    primary: "#0F172A",
    primaryPressed: "#1E293B",
    border: "#D7DEE8",
    success: "#2E7D32",
    warning: "#F59E0B",
    error: "#C62828",
  },
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
    title: {
      fontSize: 28,
      lineHeight: 34,
      fontWeight: "700",
      color: "#0F172A",
    },
    h1: {
      fontSize: 22,
      lineHeight: 30,
      fontWeight: "700",
      color: "#0F172A",
    },
    h2: {
      fontSize: 17,
      lineHeight: 24,
      fontWeight: "600",
      color: "#0F172A",
    },
    body: {
      fontSize: 15,
      lineHeight: 22,
      fontWeight: "400",
      color: "#334155",
    },
    bodySmall: {
      fontSize: 14,
      lineHeight: 20,
      fontWeight: "400",
      color: "#334155",
    },
    caption: {
      fontSize: 12,
      lineHeight: 17,
      fontWeight: "400",
      color: "#64748B",
    },
    button: {
      fontSize: 16,
      lineHeight: 22,
      fontWeight: "600",
      color: "#FFFFFF",
    },
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
  button: {
    primary: {
      container: {
        backgroundColor: "#0F172A",
        borderColor: "#0F172A",
      },
      text: {
        color: "#FFFFFF",
      },
    },
    secondary: {
      container: {
        backgroundColor: "#FFFFFF",
        borderColor: "#D7DEE8",
      },
      text: {
        color: "#0F172A",
      },
    },
    danger: {
      container: {
        backgroundColor: "#C62828",
        borderColor: "#C62828",
      },
      text: {
        color: "#FFFFFF",
      },
    },
    ghost: {
      container: {
        backgroundColor: "transparent",
        borderColor: "transparent",
      },
      text: {
        color: "#334155",
      },
    },
  },
};

export const screenPadding = tokens.spacing.xl;
export const touchTargetMin = 44;
export const inputHeights = {
  sm: 40,
  md: 48,
  lg: 56,
} as const;
