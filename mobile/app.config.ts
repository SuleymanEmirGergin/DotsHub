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
    plugins: ["expo-router", "expo-font"],
    extra: {
      API_BASE: process.env.API_BASE ?? "http://localhost:8000",
      USE_MOCK: process.env.USE_MOCK ?? "false",
      PRIVACY_URL: process.env.EXPO_PUBLIC_PRIVACY_URL ?? "",
    },
  },
};
