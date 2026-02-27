"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Locale } from "./index";
import { getText, setLocale as setLocaleImpl } from "./index";

type I18nContextValue = {
  t: (key: string) => string;
  locale: Locale;
  setLocale: (locale: Locale) => void;
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

  useEffect(() => {
    setLocaleImpl(defaultLocale);
  }, [defaultLocale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    setLocaleImpl(next);
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({
      t: (key: string) => getText(locale, key),
      locale,
      setLocale,
    }),
    [locale, setLocale]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      t: (key: string) => getText(key),
      locale: "tr",
      setLocale: setLocaleImpl,
    };
  }
  return ctx;
}
