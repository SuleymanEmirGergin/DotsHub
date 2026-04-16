import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import { View } from "react-native";
import { ErrorBoundary } from "@/src/components/ErrorBoundary";
import { OfflineBanner } from "@/src/components/OfflineBanner";
import { I18nProvider } from "@/i18n/I18nProvider";
import { getDefaultLocale } from "@/i18n/defaultLocale";
import type { Locale } from "@/i18n/index";

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [initialLocale, setInitialLocale] = useState<Locale | null>(null);

  useEffect(() => {
    const t = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(t);
  }, []);

  const resolvedRef = useRef(false);
  useEffect(() => {
    let cancelled = false;
    getDefaultLocale().then((locale) => {
      if (!cancelled) {
        resolvedRef.current = true;
        setInitialLocale(locale);
      }
    });
    const t = setTimeout(() => {
      if (!cancelled && !resolvedRef.current) setInitialLocale("tr");
    }, 2000);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, []);

  if (!ready || initialLocale === null) return null;

  return (
    <I18nProvider defaultLocale={initialLocale}>
      <ErrorBoundary onRetry={() => {}}>
        <StatusBar style="dark" />
        <View style={{ flex: 1 }}>
          <OfflineBanner />
          <View style={{ flex: 1 }}>
          <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#FAFAFA" },
          headerTintColor: "#111",
          headerTitleStyle: { fontWeight: "600", fontSize: 18 },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: "#FAFAFA" },
        }}
      >
        <Stack.Screen
          name="index"
          options={{
            title: "Dotshub",
            headerShown: false,
          }}
        />
        <Stack.Screen
          name="language"
          options={{
            title: "Dil",
            headerShown: true,
          }}
        />
      </Stack>
          </View>
        </View>
      </ErrorBoundary>
    </I18nProvider>
  );
}
