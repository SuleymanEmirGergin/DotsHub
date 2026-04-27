import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * EmptyState — replaces the `<td colSpan="6"><div>Sessions yok</div></td>`
 * pattern across audited pages.
 *
 * a11y review #15: empty rows should carry an icon, a heading, a
 * description, and an optional CTA. Screen reader users land on a
 * heading-anchored region; sighted users see the same intent at a
 * glance.
 *
 * Used inline in a `<tbody>`, wrap in a single `<tr><td colSpan>` row
 * — the component itself is layout-agnostic.
 */

export interface EmptyStateProps {
  /** Optional inline SVG / icon component. Sized at 32px by default;
   * pass your own at any size by setting className/style on the icon. */
  icon?: React.ReactNode;
  title: string;
  /** Optional secondary line. Keep short (1-2 lines). */
  description?: React.ReactNode;
  /** Optional CTA — usually a Button or a Link styled as a button.
   * Renders below the description. */
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex flex-col items-center justify-center text-center gap-3 py-12 px-6 text-muted-foreground",
        className
      )}
    >
      {icon && (
        <div
          aria-hidden="true"
          className="text-muted-foreground/60 [&_svg]:size-8"
        >
          {icon}
        </div>
      )}
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground max-w-md">
            {description}
          </p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
