/**
 * Magic-link auth helpers for staging e2e.
 *
 * Two different entry points:
 *
 * 1. `generateMagicLink()` — uses Service Role's
 *    `auth.admin.generateLink({ type: "magiclink" })` to mint the real
 *    callback URL without going through email. Tests drive Playwright
 *    to this URL so we exercise the actual PKCE + session-establishment
 *    flow end-to-end.
 *
 * 2. `ensureTestAdmin()` — idempotent: creates the auth user if missing
 *    then ensures an `admin_users` row exists so `requireAdmin()` lets
 *    the test session through.
 *
 * We intentionally do NOT inject cookies directly — the user asked for
 * the real magic-link flow to be tested, so every authenticated test
 * flows through `/auth/callback`.
 */
import type { SupabaseClient } from "@supabase/supabase-js";

export interface TestAdmin {
  id: string;
  email: string;
}

/**
 * Idempotently provision the test admin user.
 *
 * `admin.createUser` with `email_confirm: true` skips email verification
 * so the user is immediately usable. On conflict (already exists) we
 * look the user up instead.
 */
export async function ensureTestAdmin(
  sb: SupabaseClient,
  email: string,
  role: string = "admin",
): Promise<TestAdmin> {
  // Try to create; if already exists, look up.
  const { data: created, error: createErr } = await sb.auth.admin.createUser({
    email,
    email_confirm: true,
    user_metadata: { e2e_test_admin: true },
  });

  let userId: string | undefined = created?.user?.id;

  if (createErr && !/already|exists|registered/i.test(createErr.message)) {
    throw new Error(`ensureTestAdmin createUser failed: ${createErr.message}`);
  }

  if (!userId) {
    // Look it up (admin list paginated — we filter by email).
    const { data: list, error: listErr } = await sb.auth.admin.listUsers({
      page: 1,
      perPage: 200,
    });
    if (listErr) {
      throw new Error(`ensureTestAdmin listUsers failed: ${listErr.message}`);
    }
    const found = list.users.find((u) => u.email?.toLowerCase() === email.toLowerCase());
    if (!found) {
      throw new Error(`ensureTestAdmin: user ${email} neither created nor found`);
    }
    userId = found.id;
  }

  // Upsert into admin_users. `user_id` is FK to auth.users(id), UNIQUE.
  const { error: upsertErr } = await sb
    .from("admin_users")
    .upsert(
      { user_id: userId, email, role },
      { onConflict: "user_id", ignoreDuplicates: false },
    );
  if (upsertErr) {
    throw new Error(`ensureTestAdmin upsert admin_users: ${upsertErr.message}`);
  }

  return { id: userId, email };
}

/**
 * Generate the real magic-link callback URL without sending email.
 *
 * @param redirectTo Path or URL to append as `redirect_to=` — Playwright
 *   navigates to the returned link, which triggers Supabase's
 *   `/auth/v1/verify` → redirects to our `/auth/callback?code=…` →
 *   our app exchanges the code for a session.
 */
export async function generateMagicLink(
  sb: SupabaseClient,
  email: string,
  redirectTo: string,
): Promise<string> {
  const { data, error } = await sb.auth.admin.generateLink({
    type: "magiclink",
    email,
    options: { redirectTo },
  });
  if (error) {
    throw new Error(`generateMagicLink failed: ${error.message}`);
  }
  const actionLink = data?.properties?.action_link;
  if (!actionLink) {
    throw new Error("generateMagicLink: action_link missing from response");
  }
  return actionLink;
}
