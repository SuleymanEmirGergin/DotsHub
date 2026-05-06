/**
 * Health-tourism flow dispatcher.
 *
 * Routes by `quoteStore.step`. Mirrors the index.tsx pattern used by
 * the triage flow: each step is a self-contained screen, the
 * dispatcher just picks which one to render.
 */
import React, { useEffect } from "react";
import { router } from "expo-router";
import { useI18n } from "@/i18n/I18nProvider";
import { useQuoteStore } from "@/src/state/quoteStore";

import ProcedureBrowseScreen from "./ProcedureBrowseScreen";
import PatientProfileScreen from "./PatientProfileScreen";
import QuoteResultScreen from "./QuoteResultScreen";
import ItineraryScreen from "./ItineraryScreen";
import LeadFormScreen from "./LeadFormScreen";
import LeadSuccessScreen from "./LeadSuccessScreen";
import NotFitScreen from "./NotFitScreen";
import HtErrorScreen from "./HtErrorScreen";

export default function HtFlowScreen() {
  const step = useQuoteStore((s) => s.step);
  const setLocale = useQuoteStore((s) => s.setLocale);
  const { locale } = useI18n();

  // Keep the store's locale snapshot in sync with the app locale so
  // every API call sends the user's current language. We only sync
  // here (flow root) so a mid-flow language switch doesn't change
  // the locale of an already-cached idempotent reply mid-step.
  useEffect(() => {
    const map: Record<string, "tr-TR" | "en-US" | "de-DE" | "ru-RU" | "ar-SA"> = {
      tr: "tr-TR",
      en: "en-US",
      de: "de-DE",
      ru: "ru-RU",
      ar: "ar-SA",
    };
    setLocale(map[locale] ?? "tr-TR");
  }, [locale, setLocale]);

  // Default exit: when the user resets and lands on browse, leaving
  // the quote route should bring them back to the triage entry.
  // Handled by expo-router's stack pop — nothing to do here.

  switch (step) {
    case "browse":
      return <ProcedureBrowseScreen onExit={() => router.back()} />;
    case "profile":
      return <PatientProfileScreen />;
    case "quote":
      return <QuoteResultScreen />;
    case "itinerary":
      return <ItineraryScreen />;
    case "lead":
      return <LeadFormScreen />;
    case "success":
      return <LeadSuccessScreen onExit={() => router.back()} />;
    case "not_fit":
      return <NotFitScreen onExit={() => router.back()} />;
    case "error":
      return <HtErrorScreen />;
    default:
      return <ProcedureBrowseScreen onExit={() => router.back()} />;
  }
}
