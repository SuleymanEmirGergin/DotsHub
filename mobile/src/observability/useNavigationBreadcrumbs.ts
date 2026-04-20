/**
 * React hook: emits a `navigation` breadcrumb whenever the current
 * pathname changes. Mounted at the root layout so every route
 * transition the user experiences shows up in the Sentry breadcrumb
 * trail.
 *
 * Why the useRef guard:
 *   expo-router's `usePathname` re-renders on every nav event. We
 *   only want one breadcrumb per UNIQUE pathname change — a parent
 *   re-render triggered by, say, a state change on the same route
 *   must not produce a phantom "→ /" crumb.
 *
 * Why we don't track params:
 *   Query/path params can carry session UUIDs or similar. `breadcrumb`
 *   already applies `redactUrlPath` for /v1/session/ URLs, but the
 *   mobile route space is small and we prefer to KEEP parameters out
 *   entirely vs. scrub case-by-case. If you later want them, run
 *   them through `redactPII` from `./redact` before passing in.
 */

import { useEffect, useRef } from "react";
import { usePathname } from "expo-router";

import { addNavigationBreadcrumb } from "./breadcrumb";

export function useNavigationBreadcrumbs(): void {
  const pathname = usePathname();
  const prev = useRef<string | null>(null);

  useEffect(() => {
    if (pathname === prev.current) return;
    // First render: prev is null, `from` is null which matches the
    // cold-start shape the breadcrumb helper renders as "-> pathname".
    addNavigationBreadcrumb(pathname, prev.current);
    prev.current = pathname;
  }, [pathname]);
}
