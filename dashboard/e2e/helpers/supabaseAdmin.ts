/**
 * Service-Role Supabase client for e2e setup/teardown.
 *
 * Bypasses RLS — only used by:
 *   - globalSetup: upsert admin_users row, seed triage_sessions
 *   - globalTeardown: delete rows marked with the run id
 *   - auth helper: mint an admin-generated magic link for the test user
 *
 * Never import this from Playwright page contexts. Tests themselves should
 * hit the app like a real user (via baseURL), not poke Supabase directly.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export function supabaseAdmin(): SupabaseClient {
  const url = process.env.STAGING_SUPABASE_URL ?? process.env.SUPABASE_URL;
  const key = process.env.STAGING_SUPABASE_SERVICE_ROLE_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error(
      "Staging e2e requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY. " +
        "Fill dashboard/.env.staging (see .env.staging.example) or set the " +
        "CI secret matrix (STAGING_SUPABASE_URL / STAGING_SUPABASE_SERVICE_ROLE_KEY).",
    );
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
