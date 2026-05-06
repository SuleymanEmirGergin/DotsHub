/**
 * htMock contract — the offline mock must produce shape-valid
 * envelopes for all three endpoints. Lets the HT screens render in
 * USE_MOCK builds (Storybook / preview) without a real backend.
 */
import { mockQuote, mockItinerary, mockLead } from "../../src/api/mock/htMock";

describe("htMock", () => {
  describe("mockQuote", () => {
    it("returns a QUOTE envelope for a known procedure", () => {
      const env = mockQuote({ procedure_id: "fue_hair_transplant" });
      expect(env.type).toBe("QUOTE");
      if (env.type === "QUOTE") {
        expect(env.payload.quote_id).toMatch(/^quote_/);
        expect(env.payload.procedure.id).toBe("fue_hair_transplant");
        expect(env.payload.procedure.name_tr).toBe("FUE Saç Ekimi");
        expect(env.payload.clinics.length).toBeGreaterThan(0);
        expect(env.payload.currency).toBe("EUR");
      }
    });

    it("routes to EMERGENCY when recent_mi flag is on", () => {
      const env = mockQuote({
        procedure_id: "fue_hair_transplant",
        profile: { recent_mi: true },
      });
      expect(env.type).toBe("EMERGENCY");
      if (env.type === "EMERGENCY") {
        expect(env.payload.urgency).toBe("ROUTINE_BUT_NOT_TRAVEL_FIT");
        expect(env.payload.fit_to_travel_warnings[0].severity).toBe("block");
      }
    });

    it("returns ERROR for an unknown procedure id", () => {
      const env = mockQuote({ procedure_id: "made_up_thing" });
      expect(env.type).toBe("ERROR");
      if (env.type === "ERROR") {
        expect(env.payload.code).toBe("PROCEDURE_UNRESOLVED");
      }
    });

    it("surfaces a warn-level fit-to-travel item for bmi_over_35", () => {
      const env = mockQuote({
        procedure_id: "fue_hair_transplant",
        profile: { bmi_over_35: true },
      });
      expect(env.type).toBe("QUOTE");
      if (env.type === "QUOTE") {
        const warns = env.payload.fit_to_travel_warnings.filter(
          (w) => w.severity === "warn",
        );
        expect(warns.length).toBeGreaterThan(0);
      }
    });
  });

  describe("mockItinerary", () => {
    it("returns an ITINERARY envelope with day-by-day items", () => {
      const env = mockItinerary({
        procedure_id: "fue_hair_transplant",
        clinic_id: "clinic_istanbul_aesthetics_one",
        arrival_date: "2026-05-15",
      });
      expect(env.type).toBe("ITINERARY");
      if (env.type === "ITINERARY") {
        expect(env.payload.total_days).toBeGreaterThan(0);
        expect(env.payload.items.length).toBe(env.payload.total_days);
        expect(env.payload.items[0].category).toBe("arrival");
        expect(env.payload.items[env.payload.items.length - 1].category).toBe(
          "departure",
        );
      }
    });

    it("returns ERROR for an unknown procedure", () => {
      const env = mockItinerary({
        procedure_id: "no_such_thing",
        clinic_id: "clinic_x",
        arrival_date: "2026-05-15",
      });
      expect(env.type).toBe("ERROR");
    });
  });

  describe("mockLead", () => {
    it("returns RESULT/LEAD_ACCEPTED on submission", () => {
      const env = mockLead({
        procedure_id: "fue_hair_transplant",
        clinic_id: "clinic_istanbul_aesthetics_one",
        contact: { name: "Ali", email: "ali@x.com" },
        consent_to_share: true,
      });
      expect(env.type).toBe("RESULT");
      if (env.type === "RESULT") {
        expect(env.payload.code).toBe("LEAD_ACCEPTED");
        expect(env.payload.lead_id).toMatch(/^lead_/);
        expect(env.payload.consent_to_share).toBe(true);
        expect(env.payload.webhook_status).toBe("scheduled");
      }
    });

    it("preserves consent_to_share=false in the response", () => {
      const env = mockLead({
        procedure_id: "fue_hair_transplant",
        clinic_id: "clinic_istanbul_aesthetics_one",
        contact: {},
        consent_to_share: false,
      });
      expect(env.type).toBe("RESULT");
      if (env.type === "RESULT") {
        expect(env.payload.consent_to_share).toBe(false);
      }
    });
  });
});
