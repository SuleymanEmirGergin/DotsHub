"use client";

/**
 * Admin-scoped error boundary.
 *
 * Every page under /admin/* server-renders Supabase queries; a missing
 * SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY surfaces as a thrown
 * SupabaseEnvMissingError from supabaseAdmin(), which bubbles up to
 * Next.js and (without this file) renders the generic 404/500 screen.
 *
 * This boundary catches any admin-page exception and renders a clean
 * "not configured" state so:
 *   - The localhost Playwright smoke (no Supabase env) still sees a
 *     valid admin page with a recognizable heading.
 *   - Partial-outage deploys (env forgot to include Supabase) show
 *     an operator-readable message instead of a generic crash page.
 *
 * Specific handling for SupabaseEnvMissingError (from lib/supabaseServer
 * ); any other error falls through to a generic message + retry button.
 */

import { useEffect } from "react";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
     
    console.error("[admin error boundary]", error);
  }, [error]);

  const isSupabaseEnvMissing =
    error.name === "SupabaseEnvMissingError" ||
    /SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY/.test(error.message);

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 max-w-[720px] mx-auto text-center">
      {isSupabaseEnvMissing ? (
        <>
          <h1 className="text-2xl font-bold mb-3">Admin panel unavailable</h1>
          <p className="text-muted-foreground mb-4">
            Supabase is not configured in this environment. Set{" "}
            <code className="px-1 py-0.5 bg-muted rounded text-sm">
              SUPABASE_URL
            </code>{" "}
            and{" "}
            <code className="px-1 py-0.5 bg-muted rounded text-sm">
              SUPABASE_SERVICE_ROLE_KEY
            </code>{" "}
            to enable the admin console.
          </p>
          <p className="text-xs text-muted-foreground">
            Healthcare / mobile client features still work — the admin
            dashboard is the only surface that requires Supabase.
          </p>
        </>
      ) : (
        <>
          <h1 className="text-2xl font-bold mb-3">Something went wrong</h1>
          <p className="text-muted-foreground mb-4">
            {error.message || "An unexpected error occurred."}
          </p>
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium shadow-sm hover:bg-muted"
          >
            Try again
          </button>
        </>
      )}
    </div>
  );
}
