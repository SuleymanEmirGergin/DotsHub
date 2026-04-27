import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * FilterTab — link styled as a toggle pill, used for URL-driven
 * filter sets (sessions: all/up/down; future: review_status,
 * upload_kind, etc.).
 *
 * Promoted from `feedback/page.tsx` local definition + reuses the
 * inline pattern in sessions/page.tsx. Renders as `<a>` (NOT
 * `<button>`) because URL state preserves filter on share/refresh —
 * the right call per a11y review #11.
 *
 * Touch target: `min-h-11` (44px) — addresses a11y review #12 (was
 * ~36px). Vertical padding stays `py-2` for visual density on
 * desktop; `min-h` brings it up to 44 on touch-coarse media.
 */

const filterTabVariants = cva(
  "inline-flex items-center justify-center min-h-9 md:min-h-11 px-4 py-2 rounded-md border text-sm font-semibold no-underline transition-colors",
  {
    variants: {
      active: {
        true: "",
        false: "bg-card text-foreground border-border hover:bg-accent",
      },
      tone: {
        // Default neutral active state — solid primary
        primary:
          "data-[active=true]:bg-primary data-[active=true]:text-primary-foreground data-[active=true]:border-primary",
        // Success / warning / destructive tones for filters that
        // semantically map to a status (e.g. "up" feedback → success)
        success:
          "data-[active=true]:bg-success data-[active=true]:text-success-foreground data-[active=true]:border-success",
        warning:
          "data-[active=true]:bg-warning data-[active=true]:text-warning-foreground data-[active=true]:border-warning",
        destructive:
          "data-[active=true]:bg-destructive data-[active=true]:text-destructive-foreground data-[active=true]:border-destructive",
      },
    },
    defaultVariants: {
      active: false,
      tone: "primary",
    },
  }
);

export interface FilterTabProps
  extends React.AnchorHTMLAttributes<HTMLAnchorElement>,
    VariantProps<typeof filterTabVariants> {
  href: string;
  active: boolean;
  /** Optional leading icon (lucide-style). */
  icon?: React.ReactNode;
}

export const FilterTab = React.forwardRef<HTMLAnchorElement, FilterTabProps>(
  ({ href, active, tone, icon, className, children, ...props }, ref) => {
    return (
      <a
        ref={ref}
        href={href}
        data-active={active ? "true" : "false"}
        aria-current={active ? "page" : undefined}
        className={cn(
          filterTabVariants({ active, tone }),
          "gap-1.5",
          className
        )}
        {...props}
      >
        {icon && <span aria-hidden="true">{icon}</span>}
        {children}
      </a>
    );
  }
);
FilterTab.displayName = "FilterTab";

export { filterTabVariants };
