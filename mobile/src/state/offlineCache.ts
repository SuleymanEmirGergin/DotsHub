/**
 * Offline triage-result cache.
 *
 * Persists the last N (default 10) RESULT / EMERGENCY envelopes the user
 * has seen, so the history screen can still show *something* when the
 * device is offline or the backend is unreachable.
 *
 * Storage layout:
 *   key: `@triaige/cachedResults`
 *   value: JSON-serialised array of `CachedSession` ordered newest-first.
 *
 * We follow the same AsyncStorage-optional pattern used in
 * `i18n/storage.ts`: a `Function("return require")` safe-require that
 * falls back to a module-scoped `memoryStore` Map when the native module
 * isn't present (tests, web, constrained environments). That way the
 * cache is transparent in unit tests without requiring jest mocks of
 * `@react-native-async-storage/async-storage`.
 *
 * NOTE: this cache is intentionally flat & bounded. We do NOT persist
 * per-session question history, free-text bodies, or full assistant
 * dialogue — just the summary the history list needs: date, envelope
 * type, specialty, and the confidence chip. If we ever want a full
 * offline "re-open" flow we'll add a second per-session blob keyed by
 * session_id; keeping them separate avoids blowing up the list-screen
 * payload every time the user taps one item.
 */
import type {
  EmergencyPayload,
  Envelope,
  ResultPayload,
} from "./types";

const CACHE_STORAGE_KEY = "@triaige/cachedResults";
const MAX_ENTRIES = 10;
const memoryStore = new Map<string, string>();

type AsyncStorageLike = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem?: (key: string) => Promise<void>;
};

let asyncStorageRef: AsyncStorageLike | null | undefined;

function getAsyncStorage(): AsyncStorageLike | null {
  if (asyncStorageRef !== undefined) return asyncStorageRef;
  try {
    // Optional dependency — absent in jest / web / constrained envs.
    const safeRequire = Function("return require")() as (
      name: string,
    ) => unknown;
    const mod = safeRequire(
      "@react-native-async-storage/async-storage",
    ) as { default?: unknown };
    const candidate = (mod?.default ?? mod) as Partial<AsyncStorageLike>;
    if (
      candidate &&
      typeof candidate.getItem === "function" &&
      typeof candidate.setItem === "function"
    ) {
      asyncStorageRef = candidate as AsyncStorageLike;
      return asyncStorageRef;
    }
  } catch {
    // ignore
  }
  asyncStorageRef = null;
  return asyncStorageRef;
}

/**
 * Flat snapshot mirroring the `SessionItem` shape the HistoryScreen
 * renders. Anything beyond this is lossy on purpose (see file header).
 */
export type CachedSession = {
  /** stable synthetic id — session_id when available, else cached-ts */
  id: string;
  created_at: string; // ISO8601
  envelope_type: "RESULT" | "EMERGENCY";
  recommended_specialty_tr?: string;
  confidence_label_tr?: string;
  confidence_0_1?: number;
  stop_reason?: string;
};

async function readStorage(): Promise<CachedSession[]> {
  try {
    const storage = getAsyncStorage();
    const raw = storage
      ? await storage.getItem(CACHE_STORAGE_KEY)
      : memoryStore.get(CACHE_STORAGE_KEY) ?? null;
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Defensive: drop any entries that don't look like our shape.
    return parsed.filter(
      (e): e is CachedSession =>
        !!e &&
        typeof e.id === "string" &&
        typeof e.created_at === "string" &&
        (e.envelope_type === "RESULT" || e.envelope_type === "EMERGENCY"),
    );
  } catch {
    return [];
  }
}

async function writeStorage(entries: CachedSession[]): Promise<void> {
  try {
    const storage = getAsyncStorage();
    const serialised = JSON.stringify(entries);
    if (storage) {
      await storage.setItem(CACHE_STORAGE_KEY, serialised);
    } else {
      memoryStore.set(CACHE_STORAGE_KEY, serialised);
    }
  } catch {
    // ignore — offline cache is best-effort, never fatal.
  }
}

/**
 * Read every cached session, newest first. Never throws.
 */
export async function getCachedResults(): Promise<CachedSession[]> {
  return readStorage();
}

/**
 * Persist the given envelope as a cached summary. No-op for envelope
 * types we don't summarise (QUESTION / ERROR). When the cache is full
 * we drop the oldest entry (FIFO).
 *
 * Dedupe: if an entry with the same `session_id` already exists we
 * replace it (so re-running the final turn of the same session won't
 * create duplicate rows in the history list).
 */
export async function saveResult(env: Envelope): Promise<void> {
  if (env.type !== "RESULT" && env.type !== "EMERGENCY") return;

  const entry = envelopeToCached(env);
  if (!entry) return;

  const existing = await readStorage();
  const deduped = existing.filter((e) => e.id !== entry.id);
  const next = [entry, ...deduped].slice(0, MAX_ENTRIES);
  await writeStorage(next);
}

/**
 * Wipe the cache. Used by the sign-out / "clear my data" flow and
 * exposed so tests can reset state between cases.
 */
export async function clearCachedResults(): Promise<void> {
  try {
    const storage = getAsyncStorage();
    if (storage && typeof storage.removeItem === "function") {
      await storage.removeItem(CACHE_STORAGE_KEY);
    } else if (storage) {
      await storage.setItem(CACHE_STORAGE_KEY, "[]");
    } else {
      memoryStore.delete(CACHE_STORAGE_KEY);
    }
  } catch {
    // ignore
  }
}

/**
 * Test-only: reset the cached AsyncStorage reference so subsequent
 * calls re-resolve the native module. Also clears the in-memory
 * fallback.
 */
export function __resetOfflineCacheForTests(): void {
  asyncStorageRef = undefined;
  memoryStore.clear();
}

// ─── Mapping helpers ───────────────────────────────────────────────

function envelopeToCached(env: Envelope): CachedSession | null {
  if (env.type === "RESULT") {
    const payload = env.payload as ResultPayload;
    return {
      id: env.session_id ?? `cached-${Date.now()}`,
      created_at: new Date().toISOString(),
      envelope_type: "RESULT",
      recommended_specialty_tr: payload.recommended_specialty?.name_tr,
      confidence_label_tr: payload.confidence_label_tr,
      confidence_0_1: payload.confidence_0_1,
      stop_reason: payload.stop_reason,
    };
  }
  if (env.type === "EMERGENCY") {
    const payload = env.payload as EmergencyPayload;
    return {
      id: env.session_id ?? `cached-${Date.now()}`,
      created_at: new Date().toISOString(),
      envelope_type: "EMERGENCY",
      // Emergency envelopes don't carry a specialty / confidence chip;
      // we synthesise the summary from the reason so the history card
      // still renders a line instead of empty.
      recommended_specialty_tr: payload.reason_tr,
    };
  }
  return null;
}
