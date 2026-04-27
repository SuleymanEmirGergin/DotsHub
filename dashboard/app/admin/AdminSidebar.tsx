"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

/**
 * AdminSidebar — left rail nav across every /admin/* page.
 *
 * Replaces the per-page hardcoded cross-link header that the
 * design baseline flagged as the dashboard's #1 navigation pain
 * (every page repeated the link list with a different ordering).
 * One source of truth here.
 *
 * Track A's new pages (uploads, operators, leads) are listed but
 * may 404 until their respective implementation commits land. That's
 * acceptable for the pre-launch phase: PATIENT_UPLOAD_ENABLED stays
 * default off, and dev / staging operators see the expected "page
 * not yet built" 404 instead of being confused why the link isn't
 * there.
 *
 * Active-state detection is path-prefix based (e.g.
 * /admin/sessions/[id]/replay still highlights "Seanslar"), with
 * exact-match fallback for short paths like /admin.
 */

interface NavItem {
  href: string;
  labelKey: string; // i18n key under nav.*
  icon: React.ComponentType<{ className?: string }>;
  /** Optional: surfaces "(yakında)" hint when the page is documented
   * but not yet implemented. Doesn't disable the link — Next 404 is
   * the natural fallback. */
  upcoming?: boolean;
}

// ─── Lucide-style inline icons (no lucide-react dep yet) ──────────
//
// Same aria-hidden + size-4 + currentColor pattern as Badge primitive.
// Promote to lucide-react when the library lands.

const iconBaseProps = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const ChartIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);
const MessageIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);
const ListIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </svg>
);
const UploadIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);
const UsersIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);
const HospitalIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <line x1="12" y1="8" x2="12" y2="16" />
    <line x1="8" y1="12" x2="16" y2="12" />
  </svg>
);
const SettingsIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);
const ActivityIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);
const TuningIcon = ({ className }: { className?: string }) => (
  <svg {...iconBaseProps} className={className}>
    <line x1="4" y1="21" x2="4" y2="14" />
    <line x1="4" y1="10" x2="4" y2="3" />
    <line x1="12" y1="21" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12" y2="3" />
    <line x1="20" y1="21" x2="20" y2="16" />
    <line x1="20" y1="12" x2="20" y2="3" />
    <line x1="1" y1="14" x2="7" y2="14" />
    <line x1="9" y1="8" x2="15" y2="8" />
    <line x1="17" y1="16" x2="23" y2="16" />
  </svg>
);

// ─── Nav config ────────────────────────────────────────────────────
//
// Two sections: triage (existing) + track-A (new). Adding a new page
// is one entry in this array; cross-page link-list drift is now
// impossible because every page reads from the same source.

interface NavSection {
  titleKey: string; // optional section title (i18n key under nav.section.*)
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    titleKey: "section.triage",
    items: [
      { href: "/admin/analytics", labelKey: "analytics", icon: ChartIcon },
      { href: "/admin/feedback", labelKey: "feedback", icon: MessageIcon },
      { href: "/admin/sessions", labelKey: "sessions", icon: ListIcon },
      { href: "/admin/live", labelKey: "live", icon: ActivityIcon },
    ],
  },
  {
    titleKey: "section.track_a",
    items: [
      { href: "/admin/uploads", labelKey: "uploads", icon: UploadIcon, upcoming: true },
      { href: "/admin/operators", labelKey: "operators", icon: UsersIcon, upcoming: true },
      { href: "/admin/leads", labelKey: "leads", icon: HospitalIcon, upcoming: true },
    ],
  },
  {
    titleKey: "section.ops",
    items: [
      { href: "/admin/tuning-tasks", labelKey: "tuningTasks", icon: TuningIcon },
      { href: "/admin/tenants", labelKey: "tenants", icon: UsersIcon },
      { href: "/admin/status", labelKey: "status", icon: SettingsIcon },
    ],
  },
];

interface AdminSidebarProps {
  /** Resolved labels map keyed on the nav.* sub-key. Server passes
   * this so the sidebar stays a client component (for usePathname)
   * but doesn't pull i18n into the client bundle. */
  labels: Record<string, string>;
}

function isActive(href: string, pathname: string | null): boolean {
  if (!pathname) return false;
  if (pathname === href) return true;
  // Prefix match for nested routes (e.g. /admin/sessions/[id]/replay)
  return pathname.startsWith(href + "/");
}

export function AdminSidebar({ labels }: AdminSidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className="hidden md:flex md:flex-col md:w-60 md:shrink-0 border-r border-border bg-card sticky md:top-[57px] md:self-start md:max-h-[calc(100vh-57px)] md:overflow-y-auto"
      aria-label={labels["sidebar"] ?? "Yönetim menüsü"}
    >
      <nav className="py-4 px-3 flex flex-col gap-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.titleKey} className="flex flex-col gap-0.5">
            {labels[section.titleKey] && (
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-3 pb-1.5">
                {labels[section.titleKey]}
              </div>
            )}
            {section.items.map((item) => {
              const active = isActive(item.href, pathname);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors no-underline",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground hover:bg-muted"
                  )}
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="flex-1">
                    {labels[item.labelKey] ?? item.labelKey}
                  </span>
                  {item.upcoming && !active && (
                    <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wide">
                      {labels["upcoming"] ?? "yakında"}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}
