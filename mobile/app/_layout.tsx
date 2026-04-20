import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import { View } from "react-native";
import { ErrorBoundary } from "@/src/components/ErrorBoundary";
import { OfflineBanner } from "@/src/components/OfflineBanner";
import { VersionBlockScreen } from "@/src/components/VersionBlockScreen";
import { VersionUpdateBanner } from "@/src/components/VersionUpdateBanner";
import { useVersionGate } from "@/src/hooks/useVersionGate";
import { I18nProvider } from "@/i18n/I18nProvider";
import { getDefaultLocale } from "@/i18n/defaultLocale";
import type { Locale } from "@/i18n/index";
// Sentry must initialise BEFORE the router mounts so any error
// thrown during bundle eval or the first layout render is captured.
// `initSentry()` is a no-op when `EXPO_PUBLIC_SENTRY_DSN` is blank,
// so importing this module is safe in dev / OSS clones that don't
// have Sentry configured.
import { initSentry } from "@/src/observability/sentry";
import { useNavigationBreadcrumbs } from "@/src/observability/useNavigationBreadcrumbs";

initSentry();

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [initialLocale, setInitialLocale] = useState<Locale | null>(null);
  // Emits a Sentry breadcrumb on every pathname change. Mounting
  // it at the root layout means every route the user visits shows
  // up in the breadcrumb trail before any crash, giving ops the
  // "what was I doing when it broke?" context.
  useNavigationBreadcrumbs();

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
        <VersionGateWrapper>
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
        </VersionGateWrapper>
      </ErrorBoundary>
    </I18nProvider>
  );
}

/**
 * Gate wrapper — reads /v1/config/features once on mount and decides
 * whether to render children, prepend a warn banner, or short-circuit
 * to the hard-block screen. Safe defaults (mode=off) on any fetch
 * failure, so a backend outage cannot brick app launch.
 */
function VersionGateWrapper({ children }: { children: React.ReactNode }) {
  const gate = useVersionGate();

  if (gate.state === "block") {
    return (
      <VersionBlockScreen
        policy={gate.policy}
        currentVersion={gate.current}
      />
    );
  }

  return (
    <View style={{ flex: 1 }}>
      {gate.state === "warn" ? (
        <VersionUpdateBanner
          policy={gate.policy}
          currentVersion={gate.current}
        />
      ) : null}
      <View style={{ flex: 1 }}>{children}</View>
    </View>
  );
}
