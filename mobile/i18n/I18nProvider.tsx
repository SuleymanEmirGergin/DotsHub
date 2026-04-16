"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { View } from "react-native";
import type { Locale } from "./index";
import { getText, setLocale as setLocaleImpl } from "./index";
import { setStoredLocale } from "./storage";

type I18nContextValue = {
  t: (key: string) => string;
  locale: Locale;
  setLocale: (locale: Locale) => void;
  isRTL: boolean;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({
  children,
  defaultLocale = "tr",
}: {
  children: React.ReactNode;
  defaultLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(defaultLocale);
  const isRTL = locale === "ar";

  useEffect(() => {
    setLocaleState(defaultLocale);
    setLocaleImpl(defaultLocale);
  }, [defaultLocale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    setLocaleImpl(next);
    setStoredLocale(next);
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({
      t: (key: string) => getText(locale, key),
      locale,
      setLocale,
      isRTL,
    }),
    [locale, setLocale, isRTL]
  );

  return (
    <I18nContext.Provider value={value}>
      <View style={{ flex: 1, direction: isRTL ? "rtl" : "ltr" }}>
        {children}
      </View>
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      t: (key: string) => getText("tr", key),
      locale: "tr",
      setLocale: setLocaleImpl,
      isRTL: false,
    };
  }
  return ctx;
}

/** Arapça (RTL) için metin stili; Text style'larına ekleyin: [styles.x, isRTL && RTL_TEXT_STYLE] */
export const RTL_TEXT_STYLE: { writingDirection: "rtl"; textAlign: "right" } = {
  writingDirection: "rtl",
  textAlign: "right",
};
