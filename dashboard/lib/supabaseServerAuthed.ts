import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Supabase server client that reads auth session from cookies.
 * Uses anon key so RLS policies are enforced.
 * Only admin users (in admin_users table) can read triage data.
 */
export async function supabaseServerAuthed() {
  const cookieStore = await cookies();
  type CookieToSet = {
    name: string;
    value: string;
    options?: Parameters<typeof cookieStore.set>[2];
  };

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: CookieToSet[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }: CookieToSet) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // setAll can fail in Server Components (read-only context)
            // This is expected — cookies are set by middleware/route handlers
          }
        },
      },
    },
  );
}
