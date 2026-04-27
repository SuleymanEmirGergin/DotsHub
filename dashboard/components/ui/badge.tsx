import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Badge — status pill with color + icon redundancy.
 *
 * Replaces the inline `<span className="bg-red-50 text-red-700 ...">`
 * pattern repeated across audited pages (sessions list envelope-type
 * badges, feedback rating, analytics confidence chips, sessions/[id]
 * "Klinik bilgi" chip). Color signals are paired with leading lucide-
 * style icons so color-blind users get the same signal — addresses
 * a11y review finding #4 (1.4.1 Use of Color).
 *
 * Variants:
 *   default     — neutral / muted (e.g. "draft", category labels)
 *   success     — positive outcome (RESULT envelope, feedback up)
 *   warning     — needs attention (SAME_DAY, medium confidence)
 *   destructive — error / critical (EMERGENCY, feedback down)
 *   info        — informational (QUESTION envelope, "Klinik bilgi")
 *   neutral     — explicit "no status" (alias of default for clarity
 *                 at call sites where intent is "explicitly neutral")
 *
 * The icon is rendered as inline SVG (no lucide-react dependency yet
 * — when it lands, swap each <Icon> for the corresponding lucide
 * component without touching the call sites).
 */

// Solid backgrounds (NOT opacity-modified) — the dashboard's tailwind
// config maps `bg-X` to plain `var(--X)` without an `<alpha-value>`
// placeholder, so the `bg-X/10` syntax doesn't expand. A future
// design-system commit can add tinted variants by switching the
// tailwind config to the alpha-value form across the board; for now
// solid backgrounds are predictable and AA-pass against their paired
// foreground.
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-xs font-semibold border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
  {
    variants: {
      variant: {
        default:
          "border-border bg-secondary text-secondary-foreground",
        neutral:
          "border-border bg-muted text-muted-foreground",
        success:
          "border-success bg-success text-success-foreground",
        warning:
          "border-warning bg-warning text-warning-foreground",
        destructive:
          "border-destructive bg-destructive text-destructive-foreground",
        info:
          "border-info bg-info text-info-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

// ─── Inline icons (lucide-style 24x24 viewBox, currentColor) ──────
//
// Sizes scale with text via 1em — the badge's `text-xs` (12px) yields
// a 12px icon, naturally paired. Marked `aria-hidden="true"` because
// the textual label IS the announcement; the icon is purely visual
// redundancy for color-blind users.

const iconClass = "size-3.5 shrink-0";
const iconBaseProps = {
  width: 14,
  height: 14,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  className: iconClass,
};

const SuccessIcon = () => (
  // CheckCircle
  <svg {...iconBaseProps}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
);

const WarningIcon = () => (
  // AlertTriangle
  <svg {...iconBaseProps}>
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const DestructiveIcon = () => (
  // AlertCircle
  <svg {...iconBaseProps}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

const InfoIcon = () => (
  // Info
  <svg {...iconBaseProps}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </svg>
);

const VARIANT_ICON: Record<NonNullable<BadgeProps["variant"]>, (() => React.ReactElement) | null> = {
  default: null,
  neutral: null,
  success: SuccessIcon,
  warning: WarningIcon,
  destructive: DestructiveIcon,
  info: InfoIcon,
};

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /**
   * When true, hides the leading icon and renders text only. Use
   * sparingly — defeats the color+shape redundancy. Reserved for
   * dense table cells where the icon would compress unreadably.
   */
  noIcon?: boolean;
}

export function Badge({
  className,
  variant,
  noIcon = false,
  children,
  ...props
}: BadgeProps) {
  const IconComp = !noIcon && variant ? VARIANT_ICON[variant] : null;
  return (
    <span
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    >
      {IconComp && <IconComp />}
      {children}
    </span>
  );
}

export { badgeVariants };
