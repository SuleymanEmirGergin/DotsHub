import "dotenv/config";

export default {
  expo: {
    name: "Triaige",
    slug: "triaige",
    version: "1.0.0",
    orientation: "portrait" as const,
    userInterfaceStyle: "light" as const,
    scheme: "triaige",
    splash: {
      backgroundColor: "#0A84FF",
    },
    assetBundlePatterns: ["**/*"],
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.triaige.app",
    },
    android: {
      adaptiveIcon: {
        backgroundColor: "#0A84FF",
      },
      package: "com.triaige.app",
    },
    web: {
      bundler: "metro",
      output: "static",
    },
    plugins: [
      "expo-router",
      "expo-font",
      // Sentry Expo plugin: wires native crash capture on
      // iOS/Android and (on EAS build) uploads source maps when
      // SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT are set. Dev
      // builds with a blank token skip the upload step silently.
      [
        "@sentry/react-native/expo",
        {
          url: "https://sentry.io/",
          organization: process.env.SENTRY_ORG ?? "triaige",
          project: process.env.SENTRY_PROJECT ?? "triaige-mobile-rn",
        },
      ],
    ],
    extra: {
      API_BASE: process.env.API_BASE ?? "http://localhost:8000",
      USE_MOCK: process.env.USE_MOCK ?? "false",
      PRIVACY_URL: process.env.EXPO_PUBLIC_PRIVACY_URL ?? "",
      // Sentry runtime config — EXPO_PUBLIC_* values are inlined at
      // bundle time so the mobile binary can `Sentry.init` before
      // the first network request. A blank DSN makes init a no-op.
      SENTRY_DSN: process.env.EXPO_PUBLIC_SENTRY_DSN ?? "",
      SENTRY_ENVIRONMENT:
        process.env.EXPO_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
      SENTRY_RELEASE: process.env.EXPO_PUBLIC_SENTRY_RELEASE ?? "",
    },
  },
};
