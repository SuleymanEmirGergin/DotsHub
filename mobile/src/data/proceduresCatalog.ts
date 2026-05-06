/**
 * Procedure browse-screen catalog — small client-side mirror of
 * backend/app/data/procedures.json.
 *
 * Why mirror:
 *   * Browse screen needs zero-latency render (no spinner before the
 *     user picks a procedure).
 *   * Backend's procedures.json carries lots of fields the UI doesn't
 *     need (synonyms, fit_to_travel_concerns, etc.); the browse step
 *     only renders id + name + category + price band.
 *   * The catalog drifts slowly (clinic onboarding cadence is monthly).
 *     A small mirror that needs a deliberate update each release is
 *     cheaper than a /v1/procedures endpoint we'd have to keep cached
 *     and version-gated.
 *
 * When the backend catalog changes:
 *   1. Bump `_meta.version` here in lockstep with the JSON `_meta.version`.
 *   2. If a procedure id is added or removed, update this file in the
 *      same PR — drift between "what mobile shows" and "what the
 *      backend can quote" surfaces as PROCEDURE_UNKNOWN at /v1/quote.
 */

export type ProcedureCategory =
  | "hair"
  | "dental"
  | "plastic_surgery"
  | "eye"
  | "obesity"
  | "ivf";

export type Procedure = {
  id: string;
  category: ProcedureCategory;
  name: { tr: string; en: string; de: string; ru: string; ar: string };
  /** Mid-band price in EUR (display anchor only — final price comes from /v1/quote). */
  indicative_price_eur: number;
  /** Recovery / stay summary, displayed under the name. */
  duration_days: { min_stay: number; max_stay: number; recovery_total: number };
};

export const PROCEDURES_CATALOG_VERSION = "0.1.0";

export const PROCEDURES: Procedure[] = [
  {
    id: "fue_hair_transplant",
    category: "hair",
    name: {
      tr: "FUE Saç Ekimi",
      en: "FUE Hair Transplant",
      de: "FUE Haartransplantation",
      ru: "Пересадка волос FUE",
      ar: "زراعة الشعر بتقنية FUE",
    },
    indicative_price_eur: 2200,
    duration_days: { min_stay: 3, max_stay: 5, recovery_total: 14 },
  },
  {
    id: "dhi_hair_transplant",
    category: "hair",
    name: {
      tr: "DHI Saç Ekimi",
      en: "DHI Hair Transplant",
      de: "DHI Haartransplantation",
      ru: "Пересадка волос DHI",
      ar: "زراعة الشعر بتقنية DHI",
    },
    indicative_price_eur: 3000,
    duration_days: { min_stay: 3, max_stay: 5, recovery_total: 14 },
  },
  {
    id: "rhinoplasty",
    category: "plastic_surgery",
    name: {
      tr: "Burun Estetiği",
      en: "Rhinoplasty",
      de: "Nasenoperation",
      ru: "Ринопластика",
      ar: "تجميل الأنف",
    },
    indicative_price_eur: 3500,
    duration_days: { min_stay: 7, max_stay: 10, recovery_total: 21 },
  },
  {
    id: "mommy_makeover",
    category: "plastic_surgery",
    name: {
      tr: "Mommy Makeover",
      en: "Mommy Makeover",
      de: "Mommy Makeover",
      ru: "Маммопластика и подтяжка живота",
      ar: "تجميل ما بعد الولادة",
    },
    indicative_price_eur: 6500,
    duration_days: { min_stay: 10, max_stay: 14, recovery_total: 42 },
  },
  {
    id: "dental_veneers",
    category: "dental",
    name: {
      tr: "Diş Kaplama",
      en: "Dental Veneers",
      de: "Zahnverblendungen",
      ru: "Виниры",
      ar: "قشور الأسنان",
    },
    indicative_price_eur: 3200,
    duration_days: { min_stay: 5, max_stay: 7, recovery_total: 7 },
  },
  {
    id: "dental_implant_full",
    category: "dental",
    name: {
      tr: "Tam Ağız İmplant",
      en: "Full-Mouth Implants",
      de: "All-on-Implantate",
      ru: "Полная имплантация",
      ar: "زراعة الفم الكاملة",
    },
    indicative_price_eur: 9800,
    duration_days: { min_stay: 7, max_stay: 10, recovery_total: 90 },
  },
  {
    id: "lasik",
    category: "eye",
    name: {
      tr: "LASIK Göz Cerrahisi",
      en: "LASIK Eye Surgery",
      de: "LASIK Augenlaser",
      ru: "Лазерная коррекция зрения LASIK",
      ar: "جراحة الليزك",
    },
    indicative_price_eur: 1900,
    duration_days: { min_stay: 3, max_stay: 4, recovery_total: 7 },
  },
  {
    id: "gastric_sleeve",
    category: "obesity",
    name: {
      tr: "Tüp Mide (Gastrik Sleeve)",
      en: "Gastric Sleeve",
      de: "Schlauchmagen-OP",
      ru: "Рукавная резекция желудка",
      ar: "تكميم المعدة",
    },
    indicative_price_eur: 4500,
    duration_days: { min_stay: 5, max_stay: 7, recovery_total: 30 },
  },
  {
    id: "ivf_basic",
    category: "ivf",
    name: {
      tr: "Tüp Bebek (Temel Paket)",
      en: "IVF (Basic Package)",
      de: "IVF (Grundpaket)",
      ru: "ЭКО (базовый пакет)",
      ar: "أطفال الأنابيب (الباقة الأساسية)",
    },
    indicative_price_eur: 3800,
    duration_days: { min_stay: 14, max_stay: 21, recovery_total: 21 },
  },
];

export function getProcedureById(id: string): Procedure | undefined {
  return PROCEDURES.find((p) => p.id === id);
}

export const CATEGORIES: ProcedureCategory[] = [
  "hair",
  "dental",
  "plastic_surgery",
  "eye",
  "obesity",
  "ivf",
];
