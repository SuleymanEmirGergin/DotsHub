/**
 * quoteStore state-machine tests.
 *
 * Verifies transitions:
 *   browse → profile      after pickProcedure
 *   profile → quote       after submitProfileForQuote (mock returns QUOTE)
 *   quote → not_fit       after submitProfileForQuote (recent_mi → EMERGENCY)
 *   quote → itinerary     after fetchItinerary
 *   quote/itinerary → success  after submitContactLead
 *   reset                 brings us back to browse
 */
// Force USE_MOCK so the store's API calls go through htMock.
jest.mock("../../src/config/runtime", () => ({
  API_BASE: "http://localhost",
  USE_MOCK: true,
  PRIVACY_URL: "",
}));

// expo-constants pulls in expo-modules-core which assumes a RN runtime
// (touches __DEV__). Stub the surface we actually use.
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));

// deviceId imports expo-constants + AsyncStorage; both are no-go in node.
// The store sends device_id with each request — any stable string is fine
// for unit tests.
jest.mock("../../utils/deviceId", () => ({
  getDeviceId: () => "test-device",
}));

// observability/breadcrumb hits Sentry; tests are not interested in
// sentry breadcrumb side-effects.
jest.mock("../../src/observability/breadcrumb", () => ({
  addApiBreadcrumb: () => undefined,
}));

import { useQuoteStore } from "../../src/state/quoteStore";
import { PROCEDURES } from "../../src/data/proceduresCatalog";

function freshStore() {
  useQuoteStore.getState().reset();
  return useQuoteStore;
}

describe("quoteStore", () => {
  beforeEach(() => {
    freshStore();
  });

  it("starts on browse with empty state", () => {
    const s = useQuoteStore.getState();
    expect(s.step).toBe("browse");
    expect(s.procedure).toBeNull();
    expect(s.quote).toBeNull();
  });

  it("pickProcedure → step=profile + clears stale forward state", () => {
    const proc = PROCEDURES[0];
    useQuoteStore.getState().pickProcedure(proc);
    const s = useQuoteStore.getState();
    expect(s.step).toBe("profile");
    expect(s.procedure?.id).toBe(proc.id);
    expect(s.quote).toBeNull();
    expect(s.selectedClinic).toBeNull();
  });

  it("submitProfileForQuote with healthy profile → step=quote", async () => {
    useQuoteStore.getState().pickProcedure(PROCEDURES[0]);
    await useQuoteStore.getState().submitProfileForQuote();
    const s = useQuoteStore.getState();
    expect(s.step).toBe("quote");
    expect(s.quote).not.toBeNull();
    expect(s.quote?.clinics.length).toBeGreaterThan(0);
  });

  it("submitProfileForQuote with recent_mi → step=not_fit", async () => {
    useQuoteStore.getState().pickProcedure(PROCEDURES[0]);
    useQuoteStore.getState().patchProfile({ recent_mi: true });
    await useQuoteStore.getState().submitProfileForQuote();
    const s = useQuoteStore.getState();
    expect(s.step).toBe("not_fit");
    expect(s.notFit).not.toBeNull();
    expect(s.notFit?.fit_to_travel_warnings[0].severity).toBe("block");
  });

  it("fetchItinerary advances to itinerary step", async () => {
    // Build the prerequisites: procedure + quote + selected clinic.
    useQuoteStore.getState().pickProcedure(PROCEDURES[0]);
    await useQuoteStore.getState().submitProfileForQuote();
    const clinic = useQuoteStore.getState().quote!.clinics[0];
    useQuoteStore.getState().pickClinic(clinic);

    await useQuoteStore.getState().fetchItinerary("2026-05-15");
    const s = useQuoteStore.getState();
    expect(s.step).toBe("itinerary");
    expect(s.itinerary).not.toBeNull();
    expect(s.itinerary?.items.length).toBeGreaterThan(0);
  });

  it("submitContactLead with consent → step=success", async () => {
    useQuoteStore.getState().pickProcedure(PROCEDURES[0]);
    await useQuoteStore.getState().submitProfileForQuote();
    const clinic = useQuoteStore.getState().quote!.clinics[0];
    useQuoteStore.getState().pickClinic(clinic);

    await useQuoteStore
      .getState()
      .submitContactLead(
        { name: "Ali", email: "ali@x.com", phone: "+9012" },
        true,
      );
    const s = useQuoteStore.getState();
    expect(s.step).toBe("success");
    expect(s.leadResult?.code).toBe("LEAD_ACCEPTED");
    expect(s.leadResult?.consent_to_share).toBe(true);
  });

  it("reset() returns to browse + clears all collected data", async () => {
    useQuoteStore.getState().pickProcedure(PROCEDURES[0]);
    await useQuoteStore.getState().submitProfileForQuote();
    useQuoteStore.getState().reset();
    const s = useQuoteStore.getState();
    expect(s.step).toBe("browse");
    expect(s.procedure).toBeNull();
    expect(s.quote).toBeNull();
  });

  it("emits ERROR step when no procedure is picked before submit", async () => {
    await useQuoteStore.getState().submitProfileForQuote();
    const s = useQuoteStore.getState();
    expect(s.step).toBe("error");
    expect(s.error?.code).toBe("NO_PROCEDURE");
  });
});
