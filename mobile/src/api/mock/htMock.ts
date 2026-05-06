/**
 * Mock implementations of /v1/quote, /v1/quote/itinerary, /v1/quote/lead.
 *
 * Used when EXPO_PUBLIC_USE_MOCK=true (offline dev / Storybook /
 * preview builds without a backend). The shapes mirror the real
 * envelopes closely enough that the screens render the same way.
 */

import type {
  HtEnvelope,
  ItineraryRequest,
  LeadRequest,
  QuoteRequest,
} from "@/src/state/htTypes";
import { getProcedureById } from "@/src/data/proceduresCatalog";

const SESSION_ID = "S_MOCK_HT";

function ms(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function mockQuote(req: QuoteRequest): HtEnvelope {
  const procedureId = req.procedure_id ?? "fue_hair_transplant";
  const proc = getProcedureById(procedureId);
  if (!proc) {
    return {
      type: "ERROR",
      session_id: SESSION_ID,
      turn_index: 0,
      payload: {
        code: "PROCEDURE_UNRESOLVED",
        message_tr:
          "Hangi işlem için teklif istediğinizi anlayamadık. Lütfen listeden seçin.",
        retryable: true,
      },
    };
  }

  // Pretend we have one fit-to-travel block when the user signals
  // recent_mi — drives the NotFitScreen path through the mock.
  if (req.profile?.recent_mi) {
    return {
      type: "EMERGENCY",
      session_id: SESSION_ID,
      turn_index: 0,
      payload: {
        urgency: "ROUTINE_BUT_NOT_TRAVEL_FIT",
        reason_tr:
          "Son 3 ayda kalp krizi geçirmiş hastaların elektif işlemler için seyahat etmesi önerilmez.",
        instructions_tr: [
          "Önce yerel kardiyoloji görüşmesi yapın.",
          "Stabilizasyon sonrası tekrar değerlendirme alın.",
        ],
        fit_to_travel_warnings: [
          {
            rule_id: "recent_mi_block",
            severity: "block",
            reason_tr: "Son 3 ayda geçirilmiş miyokard infarktüsü.",
            recommendation_tr: "Kardiyoloji onayı alındıktan sonra tekrar başvurun.",
          },
        ],
        procedure_id: procedureId,
        procedure_name_tr: proc.name.tr,
      },
    };
  }

  return {
    type: "QUOTE",
    session_id: SESSION_ID,
    turn_index: 0,
    payload: {
      quote_id: `quote_${ms()}`,
      procedure: {
        id: proc.id,
        name_tr: proc.name.tr,
        category: proc.category,
        duration_days: proc.duration_days,
      },
      clinics: [
        {
          clinic_id: "clinic_istanbul_aesthetics_one",
          clinic_name: "İstanbul Aesthetics One",
          city: "İstanbul",
          score_0_1: 0.93,
          price_eur: Math.round(proc.indicative_price_eur * 1.15),
          price_band_eur: { mid: proc.indicative_price_eur },
          package_features: [
            "5* otel",
            "VIP transfer",
            "Türk-Almanca-İngilizce-Rusça-Arapça çevirmen",
            "Ameliyat sonrası takip uygulaması",
          ],
          languages: ["tr", "en", "de", "ru", "ar"],
          certifications: ["JCI", "ISO_9001"],
          consult_response_hours: 4,
          average_rating_5: 4.7,
          why_recommended_tr: [
            "JCI sertifikalı + 14 yıllık deneyim",
            "5* otel + VIP transfer paketi",
          ],
        },
        {
          clinic_id: "clinic_istanbul_dental_studio",
          clinic_name: "İstanbul Dental Studio",
          city: "İstanbul",
          score_0_1: 0.81,
          price_eur: Math.round(proc.indicative_price_eur * 0.95),
          price_band_eur: { mid: proc.indicative_price_eur },
          package_features: ["4* otel", "Havalimanı transfer", "Çevirmen"],
          languages: ["tr", "en", "de", "ar"],
          certifications: ["ISO_9001"],
          consult_response_hours: 6,
          average_rating_5: 4.5,
          why_recommended_tr: ["Uygun fiyat segmenti"],
        },
      ],
      fit_to_travel_warnings:
        req.profile?.bmi_over_35
          ? [
              {
                rule_id: "bmi_over_35_warn",
                severity: "warn",
                reason_tr: "BMI 35 üzerinde — anestezi riski yüksek.",
                recommendation_tr:
                  "Anestezi öncesi obezite uzmanı görüşü almanız önerilir.",
              },
            ]
          : [],
      currency: "EUR",
      summary_tr: null,
    },
  };
}

export function mockItinerary(req: ItineraryRequest): HtEnvelope {
  const proc = getProcedureById(req.procedure_id);
  if (!proc) {
    return {
      type: "ERROR",
      session_id: SESSION_ID,
      turn_index: 0,
      payload: {
        code: "PROCEDURE_UNKNOWN",
        message_tr: "Bu prosedür kataloğumuzda yok.",
        procedure_id: req.procedure_id,
        retryable: false,
      },
    };
  }
  const totalDays = proc.duration_days.min_stay;
  const arrivalDate = new Date(req.arrival_date);
  const items = Array.from({ length: totalDays }).map((_, idx) => {
    const d = new Date(arrivalDate);
    d.setDate(d.getDate() + idx);
    const iso = d.toISOString().slice(0, 10);
    if (idx === 0) {
      return {
        day: 1,
        date: iso,
        category: "arrival",
        title_tr: "Varış + konsültasyon",
        description_tr: "Havalimanı transferi, otel yerleşimi, ön muayene.",
      };
    }
    if (idx === 1) {
      return {
        day: 2,
        date: iso,
        category: "procedure",
        title_tr: "İşlem günü",
        description_tr: "Klinikte işlem; akşam dinlenme.",
        start_hour: 9,
        end_hour: 14,
      };
    }
    if (idx === totalDays - 1) {
      return {
        day: totalDays,
        date: iso,
        category: "departure",
        title_tr: "Kontrol + dönüş",
        description_tr: "Son kontrol, dikiş bakımı, havalimanına transfer.",
      };
    }
    return {
      day: idx + 1,
      date: iso,
      category: "rest",
      title_tr: "Dinlenme",
      description_tr: "Hafif aktivite, klinikten online takip.",
    };
  });

  const departure = new Date(arrivalDate);
  departure.setDate(departure.getDate() + totalDays - 1);

  return {
    type: "ITINERARY",
    session_id: SESSION_ID,
    turn_index: 0,
    payload: {
      procedure_id: req.procedure_id,
      procedure_name_tr: proc.name.tr,
      clinic_id: req.clinic_id,
      clinic_name: "İstanbul Aesthetics One",
      clinic_city: "İstanbul",
      arrival_date: req.arrival_date,
      departure_date: departure.toISOString().slice(0, 10),
      total_days: totalDays,
      items,
      pre_op_requirements: ["Temel kan tahlili", "Donör bölge fotoğrafı"],
      post_op_no_fly_days: 3,
      post_op_followup_window_days: 14,
      fit_to_travel_warnings: [],
    },
  };
}

export function mockLead(req: LeadRequest): HtEnvelope {
  return {
    type: "RESULT",
    session_id: SESSION_ID,
    turn_index: 0,
    payload: {
      code: "LEAD_ACCEPTED",
      lead_id: `lead_${ms()}`,
      quote_id: req.quote_id ?? null,
      consent_to_share: req.consent_to_share,
      webhook_status: "scheduled",
      webhook_configured: true,
      persisted: true,
      next_steps_tr: req.consent_to_share
        ? "Klinik temsilcisi 24 saat içinde sizinle iletişime geçecektir."
        : "Verileriniz paylaşılmadı. İsterseniz onay vererek tekrar başvurabilirsiniz.",
      procedure_id: req.procedure_id,
      procedure_name_tr:
        getProcedureById(req.procedure_id)?.name.tr ?? req.procedure_id,
      clinic_id: req.clinic_id,
      clinic_name: "İstanbul Aesthetics One",
      quoted_price_eur: 2500,
    },
  };
}
