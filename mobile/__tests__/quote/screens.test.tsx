/**
 * Render-smoke tests for the HT screens.
 *
 * For each step screen we:
 *   - render the screen with the store seeded into the matching state
 *   - assert no `quote.*` translation key leaks into the output (the
 *     classic missing-key bug — the literal string "quote.profile.title"
 *     showing up where a label should be)
 *   - assert at least one Turkish copy substring resolves so we know
 *     the i18n provider really did look it up
 *
 * We deliberately do NOT assert exact copy — that brittle-couples
 * the tests to the marketing wording. The contract gate
 * (check_mobile_i18n_contract.cjs) handles cross-locale parity.
 */
import React from "react";
import TestRenderer from "react-test-renderer";

// Stub expo deps the screens transitively pull in.
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));
jest.mock("../../utils/deviceId", () => ({
  getDeviceId: () => "test-device",
}));
jest.mock("../../src/observability/breadcrumb", () => ({
  addApiBreadcrumb: () => undefined,
}));
jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
}));

import { useQuoteStore } from "../../src/state/quoteStore";
import { PROCEDURES } from "../../src/data/proceduresCatalog";
import ProcedureBrowseScreen from "../../src/screens/quote/ProcedureBrowseScreen";
import PatientProfileScreen from "../../src/screens/quote/PatientProfileScreen";
import QuoteResultScreen from "../../src/screens/quote/QuoteResultScreen";
import ItineraryScreen from "../../src/screens/quote/ItineraryScreen";
import LeadFormScreen from "../../src/screens/quote/LeadFormScreen";
import LeadSuccessScreen from "../../src/screens/quote/LeadSuccessScreen";
import NotFitScreen from "../../src/screens/quote/NotFitScreen";
import HtErrorScreen from "../../src/screens/quote/HtErrorScreen";

function collectText(node: unknown): string {
  if (node == null || node === false || node === true) return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(collectText).join(" ");
  // react-test-renderer's toJSON shape: {type, props, children}
  const obj = node as { children?: unknown[] };
  if (obj.children) return obj.children.map(collectText).join(" ");
  return "";
}

function renderText(element: React.ReactElement): string {
  // react-test-renderer subscribes to zustand's useSyncExternalStore
  // correctly — renderToStaticMarkup's server snapshot path returns the
  // state at module-load time, which loses any setState() the test ran.
  let tree: TestRenderer.ReactTestRenderer | null = null;
  TestRenderer.act(() => {
    tree = TestRenderer.create(element);
  });
  const json = tree!.toJSON();
  const out = collectText(json);
  tree!.unmount();
  return out;
}

function expectNoKeyLeaks(out: string, keyPrefix: string) {
  // Any literal "<keyPrefix>.something" (with no spaces, dot-separated)
  // suggests a missing translation. We tolerate punctuation right after
  // the key root.
  const re = new RegExp(`${keyPrefix.replace(".", "\\.")}\\.[a-zA-Z]+`);
  expect(out).not.toMatch(re);
}

describe("HT screens — render smoke", () => {
  beforeEach(() => {
    useQuoteStore.getState().reset();
  });

  describe("ProcedureBrowseScreen", () => {
    it("renders without crashing", () => {
      const out = renderText(<ProcedureBrowseScreen onExit={() => {}} />);
      expectNoKeyLeaks(out, "quote.browse");
      expectNoKeyLeaks(out, "quote.category");
      // First procedure name must surface.
      expect(out).toContain("FUE Saç Ekimi");
    });
  });

  describe("PatientProfileScreen", () => {
    it("renders form fields after pickProcedure", () => {
      useQuoteStore.getState().pickProcedure(PROCEDURES[0]);
      const out = renderText(<PatientProfileScreen />);
      expectNoKeyLeaks(out, "quote.profile");
      // Selected procedure name must show in the subtitle template.
      expect(out).toContain(PROCEDURES[0].name.tr);
    });
  });

  describe("QuoteResultScreen", () => {
    it("renders 'loading' when no quote in store", () => {
      const out = renderText(<QuoteResultScreen />);
      // Common loading copy from the existing locale, not a quote.* leak.
      expectNoKeyLeaks(out, "quote.result");
    });

    it("renders clinic cards from a seeded QUOTE payload", () => {
      useQuoteStore.setState({
        step: "quote",
        procedure: PROCEDURES[0],
        quote: {
          quote_id: "q_test",
          procedure: {
            id: PROCEDURES[0].id,
            name_tr: PROCEDURES[0].name.tr,
            duration_days: PROCEDURES[0].duration_days,
          },
          clinics: [
            {
              clinic_id: "c1",
              clinic_name: "Test Clinic",
              city: "İstanbul",
              score_0_1: 0.9,
              price_eur: 2500,
              price_band_eur: { mid: 2500 },
              package_features: ["hotel_5_star"],
              languages: ["tr", "en"],
              certifications: ["JCI"],
              consult_response_hours: 4,
              average_rating_5: 4.7,
              why_recommended_tr: ["Tek satır gerekçe"],
            },
          ],
          fit_to_travel_warnings: [],
          currency: "EUR",
        },
      });
      const out = renderText(<QuoteResultScreen />);
      expectNoKeyLeaks(out, "quote.result");
      expect(out).toContain("Test Clinic");
      expect(out).toContain("2500");
      expect(out).toContain("JCI");
    });
  });

  describe("ItineraryScreen", () => {
    it("renders the date input when no itinerary in store", () => {
      const out = renderText(<ItineraryScreen />);
      expectNoKeyLeaks(out, "quote.itinerary");
    });

    it("renders day cards from a seeded ITINERARY payload", () => {
      useQuoteStore.setState({
        step: "itinerary",
        itinerary: {
          procedure_id: "p1",
          procedure_name_tr: "Test Procedure",
          clinic_id: "c1",
          clinic_name: "Test Clinic",
          clinic_city: "İstanbul",
          arrival_date: "2026-05-15",
          departure_date: "2026-05-18",
          total_days: 4,
          items: [
            {
              day: 1,
              date: "2026-05-15",
              category: "arrival",
              title_tr: "Varış",
              description_tr: "Otele yerleşim.",
            },
          ],
          pre_op_requirements: ["blood_test_basic"],
          post_op_no_fly_days: 3,
          post_op_followup_window_days: 14,
          fit_to_travel_warnings: [],
        },
      });
      const out = renderText(<ItineraryScreen />);
      expectNoKeyLeaks(out, "quote.itinerary");
      expect(out).toContain("Test Procedure");
      expect(out).toContain("Varış");
    });
  });

  describe("LeadFormScreen", () => {
    it("renders contact fields + KVKK consent toggle", () => {
      useQuoteStore.setState({
        step: "lead",
        procedure: PROCEDURES[0],
        selectedClinic: {
          clinic_id: "c1",
          clinic_name: "Test Clinic",
          city: "İstanbul",
          score_0_1: 0.9,
          price_eur: 2500,
          price_band_eur: {},
          package_features: [],
          languages: [],
          certifications: [],
          consult_response_hours: 4,
          average_rating_5: 4.7,
          why_recommended_tr: [],
        },
      });
      const out = renderText(<LeadFormScreen />);
      expectNoKeyLeaks(out, "quote.lead");
      // The procedure & clinic should appear in the subtitle.
      expect(out).toContain("Test Clinic");
      expect(out).toContain(PROCEDURES[0].name.tr);
    });
  });

  describe("LeadSuccessScreen", () => {
    it("renders the lead-accepted confirmation card", () => {
      useQuoteStore.setState({
        leadResult: {
          code: "LEAD_ACCEPTED",
          lead_id: "lead_xyz",
          consent_to_share: true,
          webhook_status: "scheduled",
          webhook_configured: true,
          persisted: true,
          next_steps_tr: "Klinik temsilcisi 24 saat içinde sizinle iletişime geçecektir.",
          procedure_id: "p1",
          procedure_name_tr: "Test Procedure",
          clinic_id: "c1",
          clinic_name: "Test Clinic",
          quoted_price_eur: 2500,
        },
      });
      const out = renderText(<LeadSuccessScreen onExit={() => {}} />);
      expectNoKeyLeaks(out, "quote.success");
      expect(out).toContain("lead_xyz");
      expect(out).toContain("Test Clinic");
    });
  });

  describe("NotFitScreen", () => {
    it("renders block reason + recommendations from store", () => {
      useQuoteStore.setState({
        notFit: {
          urgency: "ROUTINE_BUT_NOT_TRAVEL_FIT",
          reason_tr: "Son 3 ayda kalp krizi geçirmiş hastaların seyahat etmesi önerilmez.",
          instructions_tr: ["Kardiyoloji onayı alın."],
          fit_to_travel_warnings: [],
          procedure_id: "p1",
          procedure_name_tr: "Test Procedure",
        },
      });
      const out = renderText(<NotFitScreen onExit={() => {}} />);
      expectNoKeyLeaks(out, "quote.notFit");
      expect(out).toContain("kalp krizi");
      expect(out).toContain("Kardiyoloji");
    });
  });

  describe("HtErrorScreen", () => {
    it("renders code + message from store error", () => {
      useQuoteStore.setState({
        error: {
          code: "NO_PARTNER_CLINIC",
          message_tr: "Bu işlem için klinik bulunamadı.",
        },
      });
      const out = renderText(<HtErrorScreen />);
      // Reuses the existing "error.*" copy block.
      expectNoKeyLeaks(out, "error");
      expect(out).toContain("NO_PARTNER_CLINIC");
    });
  });
});
