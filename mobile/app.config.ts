import "dotenv/config";

export default {
  expo: {
    name: "Dotshub",
    slug: "dotshub",
    version: "1.0.0",
    orientation: "portrait" as const,
    userInterfaceStyle: "light" as const,
    scheme: "dotshub",
    splash: {
      backgroundColor: "#0A84FF",
    },
    assetBundlePatterns: ["**/*"],
    ios: {
      supportsTablet: true,
      bundleIdentifier: "com.dotshub.app",
    },
    android: {
      adaptiveIcon: {
        backgroundColor: "#0A84FF",
      },
      package: "com.dotshub.app",
    },
    web: {
      bundler: "metro",
      output: "static",
    },
    plugins: ["expo-router", "expo-font"],
    extra: {
      API_BASE: process.env.API_BASE ?? "http://localhost:8000",
      USE_MOCK: process.env.USE_MOCK ?? "false",
    },
  },
};
