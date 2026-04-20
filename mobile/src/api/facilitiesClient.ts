/**
 * Client for GET /v1/facilities — specialty-aware facility discovery.
 *
 * Used by ResultScreen when the user taps "More facilities" to load
 * a ranked list of nearby hospitals/clinics for the recommended
 * specialty. Location (lat/lon) is optional; when available the
 * server returns distance_km and sorts by it.
 */

import { API_BASE, USE_MOCK } from "@/src/config/runtime";
import { fetchWithTimeout } from "./fetchWithTimeout";
import { getCurrentLocation } from "../../utils/location";

export type FacilityItem = {
  name: string;
  type: string;
  address: string;
  distance_km?: number;
  lat?: number;
  lon?: number;
  phone?: string;
};

export type FacilitiesResponse = {
  specialty_id: string;
  city: string;
  items: FacilityItem[];
  disclaimer: string;
};

export type FetchFacilitiesOpts = {
  specialty: string;
  city?: string;
  limit?: number;
  /** Skip location permission prompt; pass coords directly if known. */
  lat?: number | null;
  lon?: number | null;
  /** If true, do NOT call getCurrentLocation (e.g. user declined earlier). */
  skipLocation?: boolean;
};

export async function fetchFacilities(
  opts: FetchFacilitiesOpts,
): Promise<FacilitiesResponse> {
  if (USE_MOCK) {
    return {
      specialty_id: opts.specialty,
      city: opts.city ?? "Istanbul",
      items: [],
      disclaimer: "Mock — no facilities available in local mode.",
    };
  }

  let { lat, lon } = opts;
  if (lat == null && lon == null && !opts.skipLocation) {
    const loc = await getCurrentLocation();
    if (loc) {
      lat = loc.lat;
      lon = loc.lon;
    }
  }

  const params = new URLSearchParams();
  params.set("specialty", opts.specialty);
  if (opts.city) params.set("city", opts.city);
  if (lat != null) params.set("lat", String(lat));
  if (lon != null) params.set("lon", String(lon));
  params.set("limit", String(opts.limit ?? 10));

  const res = await fetchWithTimeout(
    `${API_BASE}/v1/facilities?${params.toString()}`,
    { method: "GET", headers: { Accept: "application/json" } },
    8000,
  );
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as FacilitiesResponse;
}

/**
 * Build a platform-agnostic map URL. Uses geo: URI for Android fallback
 * and Apple/Google Maps query URL for iOS + web. React Native's `Linking`
 * will route to the installed map app when possible.
 */
export function buildMapUrl(item: FacilityItem): string {
  if (item.lat != null && item.lon != null) {
    const q = encodeURIComponent(`${item.name}, ${item.address}`);
    return `https://www.google.com/maps/search/?api=1&query=${item.lat},${item.lon}&query_place_id=${q}`;
  }
  const q = encodeURIComponent(`${item.name}, ${item.address}`);
  return `https://www.google.com/maps/search/?api=1&query=${q}`;
}
