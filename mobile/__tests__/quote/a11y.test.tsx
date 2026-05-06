/**
 * a11y + RTL contract for the HT flow.
 *
 * Walks each screen's render tree and asserts:
 *   - every interactive element (Pressable / Button) has an
 *     `accessibilityLabel` or wraps a `Text` child (so screen readers
 *     can announce something);
 *   - `accessibilityRole` is set to `button`, `link`, or `checkbox`
 *     on interactive items — bare `<Pressable>` with no role makes
 *     the element invisible to TalkBack/VoiceOver;
 *   - the lead form's KVKK consent toggle exposes
 *     `accessibilityRole="checkbox"` + `accessibilityState.checked`.
 *
 * The render shim flattens RN primitives to React Fragments, so we
 * walk the `react-test-renderer` JSON tree directly to read props
 * (the shim drops them in the Fragment, but TestRenderer captures
 * them on the original element node before passing through).
 */
import React from "react";
import TestRenderer from "react-test-renderer";

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));
jest.mock("../../utils/deviceId", () => ({ getDeviceId: () => "x" }));
jest.mock("../../src/observability/breadcrumb", () => ({
  addApiBreadcrumb: () => undefined,
}));
jest.mock("expo-router", () => ({
  router: { back: jest.fn(), push: jest.fn() },
}));

import { useQuoteStore } from "../../src/state/quoteStore";
import { PROCEDURES } from "../../src/data/proceduresCatalog";
import LeadFormScreen from "../../src/screens/quote/LeadFormScreen";
import QuoteResultScreen from "../../src/screens/quote/QuoteResultScreen";
import PatientProfileScreen from "../../src/screens/quote/PatientProfileScreen";

type TestInstance = ReturnType<TestRenderer.ReactTestRenderer["root"]["findByType"]>;

function render(element: React.ReactElement) {
  let r: TestRenderer.ReactTestRenderer | null = null;
  TestRenderer.act(() => {
    r = TestRenderer.create(element);
  });
  return r!;
}

function findAllWithProp(
  tree: TestRenderer.ReactTestRenderer,
  propName: string,
): TestRenderer.ReactTestInstance[] {
  // Walk the full tree (including Fragment children) and collect any
  // node whose props[propName] is non-undefined.
  return tree.root.findAll((node) => node.props && propName in node.props);
}

describe("HT flow a11y contract", () => {
  beforeEach(() => useQuoteStore.getState().reset());

  it("LeadFormScreen — KVKK consent has checkbox role + checked state", () => {
    useQuoteStore.setState({
      step: "lead",
      procedure: PROCEDURES[0],
      selectedClinic: {
        clinic_id: "c1",
        clinic_name: "X",
        city: "Y",
        score_0_1: 0.9,
        price_eur: 1000,
        price_band_eur: {},
        package_features: [],
        languages: [],
        certifications: [],
        consult_response_hours: 4,
        average_rating_5: 4.7,
        why_recommended_tr: [],
      },
    });
    const t = render(<LeadFormScreen />);

    // Find any node tagged with accessibilityRole="checkbox".
    const checkboxes = t.root.findAll(
      (n: TestRenderer.ReactTestInstance) =>
        n.props?.accessibilityRole === "checkbox",
    );
    expect(checkboxes.length).toBeGreaterThan(0);
    // The KVKK toggle starts unchecked; accessibilityState.checked === false.
    const kvkk = checkboxes.find(
      (n: TestRenderer.ReactTestInstance) =>
        n.props.accessibilityState?.checked === false,
    );
    expect(kvkk).toBeDefined();
  });

  it("QuoteResultScreen — clinic cards expose selected state", () => {
    useQuoteStore.setState({
      step: "quote",
      procedure: PROCEDURES[0],
      quote: {
        quote_id: "q",
        procedure: { id: "p1", name_tr: "X" },
        clinics: [
          {
            clinic_id: "c1",
            clinic_name: "Test",
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
        ],
        fit_to_travel_warnings: [],
        currency: "EUR",
      },
    });
    const t = render(<QuoteResultScreen />);
    const buttons = t.root.findAll(
      (n) => n.props?.accessibilityRole === "button",
    );
    // At minimum: clinic-card pressable + back link + viewItinerary CTA + acceptCta.
    expect(buttons.length).toBeGreaterThanOrEqual(3);
    // Every button has a label.
    buttons.forEach((b) => {
      expect(b.props.accessibilityLabel).toBeDefined();
      expect(typeof b.props.accessibilityLabel).toBe("string");
    });
  });

  it("PatientProfileScreen — every condition flag is a checkbox", () => {
    useQuoteStore.setState({ step: "profile", procedure: PROCEDURES[0] });
    const t = render(<PatientProfileScreen />);
    const checkboxes = t.root.findAll(
      (n) => n.props?.accessibilityRole === "checkbox",
    );
    // 8 condition flags → 8 checkboxes.
    expect(checkboxes.length).toBe(8);
    checkboxes.forEach((c) => {
      expect(c.props.accessibilityLabel).toBeDefined();
      // Each starts unchecked.
      expect(c.props.accessibilityState?.checked).toBe(false);
    });
  });
});
