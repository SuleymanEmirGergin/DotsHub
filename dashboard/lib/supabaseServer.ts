import { createClient } from "@supabase/supabase-js";

/**
 * Server-side Supabase client using the Service Role key.
 * Only use in Server Components / Route Handlers — never expose to client.
 *
 * Throws a typed error when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are
 * missing so callers can catch-and-fallback (e.g. the sessions page
 * renders an empty state when env isn't configured, so the localhost
 * Playwright smoke doesn't fall through to not-found).
 *
 * Kept as non-nullable in the type signature on purpose — every other
 * call site assumes a valid client back and would need `?.` plumbing
 * otherwise. Preferred pattern for callers that want graceful fallback:
 *
 *   let sb;
 *   try { sb = supabaseAdmin(); } catch { return <EmptyState />; }
 */
export class SupabaseEnvMissingError extends Error {
  constructor() {
    super("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing");
    this.name = "SupabaseEnvMissingError";
  }
}

export function supabaseAdmin() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new SupabaseEnvMissingError();
  return createClient(url, key, { auth: { persistSession: false } });
}
