import { createClient } from "@supabase/supabase-js";

/**
 * Server-side Supabase client using the Service Role key.
 * Only use in Server Components / Route Handlers — never expose to client.
 *
 * Returns null when SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing
 * rather than building a broken client that crashes on first query.
 * Callers must guard: `const sb = supabaseAdmin(); if (!sb) return <EmptyState />`.
 *
 * Why null and not throw: in the localhost Playwright smoke (CI without
 * real Supabase), server components call this and the app must render
 * a valid page, not bomb into Next.js not-found. Returning null lets
 * pages surface a friendly "not configured" message instead.
 */
export function supabaseAdmin() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}
