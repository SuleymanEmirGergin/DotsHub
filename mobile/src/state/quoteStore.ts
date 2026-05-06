/**
 * Health-tourism flow state machine (zustand).
 *
 * The HT journey is linear by design — each step depends on data
 * collected in the previous step:
 *
 *   browse  → user picks a procedure
 *   profile → user fills age/sex/BMI/condition checkboxes
 *   quote   → backend returns ranked clinics; user picks one
 *   itinerary (optional) → backend returns day-by-day plan
 *   lead    → user fills contact + KVKK consent
 *   success → confirmation; pressing "yeni başvuru" resets
 *
 * EMERGENCY (fit-to-travel block) and ERROR are off-path states the
 * dispatcher routes to dedicated screens; the user can back up to
 * profile to adjust answers.
 *
 * Why a separate store from triageStore: HT is a fully separate flow
 * with no overlapping state. Sharing one store would mean the triage
 * dispatcher has to know about quote keys, and vice-versa. Two stores
 * = two readable state machines.
 */

import { create } from "zustand";
import {
  requestQuote,
  requestItinerary,
  submitLead,
} from "@/src/api/quoteClient";
import type {
  HealthTourismProfile,
  HtEnvelope,
  ItineraryPayload,
  LeadAcceptedPayload,
  QuotePayload,
  FitToTravelBlockPayload,
  HtErrorPayload,
  ClinicQuoteItem,
  Locale,
} from "@/src/state/htTypes";
import type { Procedure } from "@/src/data/proceduresCatalog";

export type QuoteStep =
  | "browse"
  | "profile"
  | "quote"
  | "itinerary"
  | "lead"
  | "success"
  | "not_fit"
  | "error";

type State = {
  step: QuoteStep;
  loading: boolean;
  /** Procedure picked on browse step. */
  procedure: Procedure | null;
  /** Profile filled on profile step. */
  profile: HealthTourismProfile;
  /** Last QUOTE envelope payload (for the quote screen). */
  quote: QuotePayload | null;
  /** Clinic the user picked from the quote step. */
  selectedClinic: ClinicQuoteItem | null;
  /** Last ITINERARY envelope (for itinerary screen). */
  itinerary: ItineraryPayload | null;
  /** RESULT envelope after submitLead — drives success screen. */
  leadResult: LeadAcceptedPayload | null;
  /** EMERGENCY envelope when fit-to-travel blocks travel. */
  notFit: FitToTravelBlockPayload | null;
  /** ERROR envelope (any of the three calls failed). */
  error: HtErrorPayload | null;
  /** Locale snapshot at the start of the flow. */
  locale: Locale;
  /** Session id returned from the first call (link itinerary→lead). */
  sessionId: string | null;
};

type Actions = {
  setStep: (s: QuoteStep) => void;
  pickProcedure: (p: Procedure) => void;
  patchProfile: (p: Partial<HealthTourismProfile>) => void;
  setLocale: (l: Locale) => void;

  /** Submit the profile + procedure → /v1/quote, lands on quote/not_fit/error. */
  submitProfileForQuote: () => Promise<void>;

  pickClinic: (c: ClinicQuoteItem) => void;

  /** Fetch itinerary for the picked clinic + arrival date. */
  fetchItinerary: (arrivalDateIso: string) => Promise<void>;

  /** POST /v1/quote/lead and route to success/error. */
  submitContactLead: (
    contact: { name: string; email: string; phone: string; preferred_contact?: "email" | "phone" | "whatsapp" | "any" },
    consentToShare: boolean,
    notes?: string,
  ) => Promise<void>;

  /** Reset to browse — used by "yeni başvuru" button on success. */
  reset: () => void;
};

const initial: State = {
  step: "browse",
  loading: false,
  procedure: null,
  profile: {},
  quote: null,
  selectedClinic: null,
  itinerary: null,
  leadResult: null,
  notFit: null,
  error: null,
  locale: "tr-TR",
  sessionId: null,
};

function applyEnvelope(env: HtEnvelope, set: any, get: () => State & Actions) {
  set({ sessionId: env.session_id, loading: false });

  if (env.type === "QUOTE") {
    set({
      quote: env.payload,
      step: "quote",
      notFit: null,
      error: null,
      itinerary: null,
      leadResult: null,
    });
    return;
  }
  if (env.type === "ITINERARY") {
    set({ itinerary: env.payload, step: "itinerary", error: null });
    return;
  }
  if (env.type === "RESULT") {
    set({ leadResult: env.payload, step: "success", error: null });
    return;
  }
  if (env.type === "EMERGENCY") {
    set({ notFit: env.payload, step: "not_fit", error: null });
    return;
  }
  // ERROR
  set({ error: env.payload, step: "error" });
}

export const useQuoteStore = create<State & Actions>((set, get) => ({
  ...initial,

  setStep: (s) => set({ step: s }),
  pickProcedure: (p) =>
    set({
      procedure: p,
      // Forward step gets reset so a procedure swap clears stale quote.
      quote: null,
      selectedClinic: null,
      itinerary: null,
      step: "profile",
    }),
  patchProfile: (p) => set({ profile: { ...get().profile, ...p } }),
  setLocale: (l) => set({ locale: l }),

  submitProfileForQuote: async () => {
    const { procedure, profile, locale, sessionId } = get();
    if (!procedure) {
      set({
        step: "error",
        error: { code: "NO_PROCEDURE", message_tr: "Önce bir işlem seçin." },
      });
      return;
    }
    set({ loading: true });
    const env = await requestQuote(
      {
        procedure_id: procedure.id,
        profile,
        locale,
        top_n: 5,
      },
      sessionId,
    );
    applyEnvelope(env, set, get);
  },

  pickClinic: (c) => set({ selectedClinic: c }),

  fetchItinerary: async (arrivalDateIso) => {
    const { procedure, selectedClinic, profile, locale, sessionId } = get();
    if (!procedure || !selectedClinic) {
      set({
        step: "error",
        error: {
          code: "MISSING_SELECTION",
          message_tr: "Önce işlem ve klinik seçin.",
        },
      });
      return;
    }
    set({ loading: true });
    const env = await requestItinerary(
      {
        procedure_id: procedure.id,
        clinic_id: selectedClinic.clinic_id,
        arrival_date: arrivalDateIso,
        profile,
        locale,
      },
      sessionId,
    );
    applyEnvelope(env, set, get);
  },

  submitContactLead: async (contact, consentToShare, notes) => {
    const { procedure, selectedClinic, locale, sessionId, quote } = get();
    if (!procedure || !selectedClinic) {
      set({
        step: "error",
        error: {
          code: "MISSING_SELECTION",
          message_tr: "Önce işlem ve klinik seçin.",
        },
      });
      return;
    }
    set({ loading: true });
    const env = await submitLead(
      {
        procedure_id: procedure.id,
        clinic_id: selectedClinic.clinic_id,
        contact: {
          name: contact.name,
          email: contact.email,
          phone: contact.phone,
          preferred_contact: contact.preferred_contact ?? "any",
        },
        consent_to_share: consentToShare,
        locale,
        notes,
        quote_id: quote?.quote_id,
      },
      sessionId,
    );
    applyEnvelope(env, set, get);
  },

  reset: () => set({ ...initial }),
}));
