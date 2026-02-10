/**
 * Fetch wrapper with AbortController-based timeout.
 * Essential for real backend calls — native fetch has no built-in timeout.
 */
export async function fetchWithTimeout(
  url: string,
  opts: RequestInit,
  ms = 12000,
): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    return res;
  } finally {
    clearTimeout(t);
  }
}
