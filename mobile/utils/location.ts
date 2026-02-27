/**
 * Optional user location for facility discovery.
 * Requests permission and returns coords when available.
 * Requires: npx expo install expo-location
 */
export type Coords = { lat: number; lon: number };

let cached: Coords | null = null;
let cacheTime = 0;
const CACHE_MS = 5 * 60 * 1000; // 5 min

export async function getCurrentLocation(): Promise<Coords | null> {
  if (cached && Date.now() - cacheTime < CACHE_MS) return cached;
  try {
    const { getCurrentPositionAsync, requestForegroundPermissionsAsync } =
      await import("expo-location");
    const { status } = await requestForegroundPermissionsAsync();
    if (status !== "granted") return null;
    const loc = await getCurrentPositionAsync({
      accuracy: 4, // Accuracy.Balanced
      maxAge: 60000,
    });
    if (loc?.coords) {
      cached = { lat: loc.coords.latitude, lon: loc.coords.longitude };
      cacheTime = Date.now();
      return cached;
    }
  } catch {
    // expo-location not installed or permission denied
  }
  return null;
}
