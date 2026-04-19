import { getCapabilitiesHeader } from "@/src/config/capabilities";

/**
 * Fetch wrapper with AbortController-based timeout.
 * Essential for real backend calls — native fetch has no built-in timeout.
 *
 * Also injects `X-Client-Capabilities` so every backend request
 * advertises what response shapes this build can parse. Callers may
 * still override the header via `opts.headers` if a specific call
 * needs a narrower set (rare; mostly tests).
 */
export async function fetchWithTimeout(
  url: string,
  opts: RequestInit,
  ms = 12000,
): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const headers = {
      "X-Client-Capabilities": getCapabilitiesHeader(),
      ...(opts.headers ?? {}),
    };
    const res = await fetch(url, { ...opts, headers, signal: ctrl.signal });
    return res;
  } finally {
    clearTimeout(t);
  }
}
