// Supabase SSR middleware — keeps the auth session cookie fresh.
//
// Why this file exists (H2 fix for staging e2e flake):
// -----------------------------------------------------
// `@supabase/ssr`'s cookie-backed client refreshes the session JWT
// lazily: the server-side `supabase.auth.getUser()` call notices an
// expired / near-expired token and issues a rotated one, but the
// rotation only PERSISTS if the surrounding request can write cookies
// back to the response. Server Components can't (read-only context),
// so the write is silently dropped inside
// `lib/supabaseServerAuthed.ts::setAll`. Over time — or immediately
// after the callback sets the first session — the server sees a stale
// cookie, `getUser()` returns null, and `requireAdmin()` redirects to
// /login. This is the exact failure mode the Playwright staging
// tests hit every time.
//
// The middleware runs BEFORE the RSC render. Next.js middleware has
// a writable response object, so we can call `getUser()` here to
// trigger the refresh, and the `setAll` callback writes the rotated
// cookies on the outbound response. Downstream RSCs then see a
// current session.
//
// Pattern is the canonical one from
// https://supabase.com/docs/guides/auth/server-side/nextjs — kept as
// close to upstream as possible so future upgrades are mechanical.

import { type NextRequest, NextResponse } from "next/server";
import { createServerClient, type CookieOptions } from "@supabase/ssr";

// Inline shape for the `setAll` callback — avoids the implicit-any
// ESLint rule while staying close to @supabase/ssr's own types.
type CookieToSet = { name: string; value: string; options?: CookieOptions };

export async function middleware(request: NextRequest) {
  // Graceful no-op when env isn't configured (dev without a Supabase
  // project, CI before secrets are wired, etc.). The app still
  // renders — auth-protected routes just redirect to /login, which is
  // the same behaviour you'd get with an unauthenticated session.
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    return NextResponse.next({ request });
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      // IMPORTANT: two-phase write. First mirror the cookies into the
      // request (so downstream RSCs reading cookies via headers() see
      // them), then rebuild the response and attach them there too.
      // Upstream recipe — do not simplify.
      setAll(cookiesToSet: CookieToSet[]) {
        cookiesToSet.forEach(({ name, value }: CookieToSet) =>
          request.cookies.set(name, value),
        );
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }: CookieToSet) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // Trigger token refresh if needed. The call is cheap when the
  // current token is still valid — a single JWT decode + expiry
  // check, no network hop. When a refresh IS needed, the rotated
  // cookies flow through `setAll` above onto the response.
  await supabase.auth.getUser();

  return response;
}

// Match everything except static assets + obvious non-HTML paths.
// Exclusion list mirrors the Supabase recipe so we don't burn middleware
// CPU on every PNG fetch. If you add a public-static route (e.g.
// /opengraph-image), extend this matcher — otherwise the middleware
// wakes up for it unnecessarily.
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
