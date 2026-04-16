import { createBrowserClient as createSupabaseBrowserClient } from "@supabase/ssr";

/**
 * Browser Supabase client for auth callback and client-side auth.
 * Uses cookies so the server can read the session (SSR).
 */
export function createBrowserClient() {
  return createSupabaseBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
