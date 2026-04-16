/**
 * Shared BFF proxy helper — wraps fetch with timeout + error handling.
 * All admin API proxy routes use this instead of raw fetch().
 */

export interface ProxyResult {
  data: unknown;
  status: number;
}

export async function proxyFetch(
  url: string,
  init?: RequestInit
): Promise<ProxyResult> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10_000);
    const r = await fetch(url, { ...init, signal: controller.signal });
    clearTimeout(timeoutId);
    const data = await r.json().catch(() => ({ error: "upstream_parse_error" }));
    return { data, status: r.status };
  } catch (err) {
    const message =
      err instanceof Error
        ? err.name === "AbortError"
          ? "upstream_timeout"
          : err.message
        : "upstream_unreachable";
    return { data: { error: message, code: "UPSTREAM_UNAVAILABLE" }, status: 503 };
  }
}
