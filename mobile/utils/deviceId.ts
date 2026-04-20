import Constants from "expo-constants";

// NOTE: Rename'den önce bu key `__dotshub_device_id__`'di. Değiştirdik
// çünkü tüm repo "triaige" adına geçti ve prod kullanıcı yoktu → stale
// device ID'leri rehabilitate etmeye gerek yok. Kendi dev cihazında
// bir önceki ID'yi tekrar kullanmak istersen bu sabiti geri al.
const GLOBAL_DEVICE_ID_KEY = "__triaige_device_id__";
let cachedDeviceId: string | null = null;

type ConstantsShape = {
  sessionId?: string;
  installationId?: string;
};

type GlobalShape = typeof globalThis & {
  [GLOBAL_DEVICE_ID_KEY]?: string;
};

function readConstantsId(): string {
  const constants = Constants as ConstantsShape;
  if (typeof constants.sessionId === "string" && constants.sessionId.trim()) {
    return constants.sessionId.trim();
  }
  if (typeof constants.installationId === "string" && constants.installationId.trim()) {
    return constants.installationId.trim();
  }
  return "";
}

export function getDeviceId(): string {
  if (cachedDeviceId) return cachedDeviceId;

  const constantsId = readConstantsId();
  if (constantsId) {
    cachedDeviceId = constantsId;
    return constantsId;
  }

  const globalStore = globalThis as GlobalShape;
  if (globalStore[GLOBAL_DEVICE_ID_KEY]) {
    cachedDeviceId = globalStore[GLOBAL_DEVICE_ID_KEY]!;
    return cachedDeviceId;
  }

  const fallback = "fallback-" + Math.random().toString(36).slice(2, 12);
  globalStore[GLOBAL_DEVICE_ID_KEY] = fallback;
  cachedDeviceId = fallback;
  return fallback;
}
