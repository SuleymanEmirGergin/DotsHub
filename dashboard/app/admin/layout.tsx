import { cookies } from "next/headers";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { AdminSidebar } from "./AdminSidebar";

/**
 * AdminLayout — wraps every /admin/* page with a sticky-left sidebar
 * + the existing global <header>. Server component by default;
 * delegates active-route detection to the client AdminSidebar.
 *
 * Replaces the per-page header drift flagged in the design baseline:
 * every audited page (/admin/sessions, /admin/analytics, /admin/feedback)
 * had its own hardcoded cross-link list with different ordering, link
 * count, and styling. Now there's exactly one source of truth.
 *
 * i18n: server-side resolves the labels needed by the sidebar (one
 * lookup per render, no client-side i18n bundle bloat). The sidebar
 * receives a flat Record<key, label> via props.
 */

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

const LABEL_KEYS = [
  // Section titles
  "section.triage",
  "section.track_a",
  "section.ops",
  // Items
  "analytics",
  "feedback",
  "sessions",
  "live",
  "uploads",
  "operators",
  "leads",
  "tuningTasks",
  "tenants",
  "status",
  // Misc
  "sidebar",
  "upcoming",
];

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const labels: Record<string, string> = {};
  for (const key of LABEL_KEYS) {
    labels[key] = getText(locale, `nav.${key}`);
  }

  return (
    <div className="flex min-h-[calc(100vh-57px)] bg-background">
      <AdminSidebar labels={labels} />
      <main id="main" className="flex-1 min-w-0">
        {children}
      </main>
    </div>
  );
}
