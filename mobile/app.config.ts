import "dotenv/config";

export default {
  expo: {
    name: "Triaige",
    slug: "triaige",
    version: "1.0.0",
    orientation: "portrait" as const,
    userInterfaceStyle: "light" as const,
    scheme: "triaige",
    // Icon lives at assets/icon.png (1024×1024 PNG, no alpha for iOS).
    // The file committed today is a placeholder — a solid brand-blue
    // square with a white "T" mark — kept small to keep git diffs
    // readable. Swap with the real brand icon before store submission;
    // the `assets/` layout + referencing code stay the same.
    icon: "./assets/icon.png",
    splash: {
      image: "./assets/splash-icon.png",
      resizeMode: "contain" as const,
      backgroundColor: "#0A84FF",
    },
    assetBundlePatterns: ["**/*"],
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.triaige.app",
      // iOS store submission requires explicit build number separate
      // from the semver `version` above. EAS auto-increments this
      // per build via `eas.json::production.autoIncrement`, but we
      // seed an initial value so local testing + first manual
      // submission don't error on `null`.
      buildNumber: "1",
    },
    android: {
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#0A84FF",
      },
      package: "com.triaige.app",
      // Google Play's equivalent of iOS buildNumber. Same seed
      // logic — EAS auto-increments on production builds.
      versionCode: 1,
    },
    web: {
      bundler: "metro",
      output: "static",
      favicon: "./assets/favicon.png",
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
