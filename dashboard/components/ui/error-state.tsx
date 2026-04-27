import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * ErrorState — replaces the single muted `common.error: ...` div.
 *
 * a11y review #16: error pages need an icon + heading + message +
 * recovery CTA. SR users get an `role="alert"` so it announces
 * immediately on render; sighted users get a clear visual signal
 * (destructive variant) plus a retry path.
 *
 * The retry CTA can be a server-rendered link (most common — operator
 * just refreshes), an `<form action>` for an explicit retry POST, or
 * a client `onClick` for in-page retries (lazy-loaded data, etc.).
 */

export interface ErrorStateProps {
  icon?: React.ReactNode;
  title: string;
  message?: React.ReactNode;
  /** Either a server-side href OR a client onClick. Provide one. */
  retryHref?: string;
  retryOnClick?: () => void;
  retryLabel?: string;
  /** Optional escalation hint ("Sorun devam ederse /admin/status'u
   * kontrol edin"). Rendered below the retry CTA in muted text. */
  hint?: React.ReactNode;
  className?: string;
}

export function ErrorState({
  icon,
  title,
  message,
  retryHref,
  retryOnClick,
  retryLabel = "Tekrar dene",
  hint,
  className,
}: ErrorStateProps) {
  const showRetry = retryHref || retryOnClick;

  // AlertOctagon-style fallback icon (lucide).
  const defaultIcon = (
    <svg
      width={32}
      height={32}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="size-8"
    >
      <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "flex flex-col items-center justify-center text-center gap-3 py-12 px-6",
        className
      )}
    >
      <div
        aria-hidden="true"
        className="text-destructive [&_svg]:size-8"
      >
        {icon ?? defaultIcon}
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {message && (
          <p className="text-sm text-muted-foreground max-w-md">{message}</p>
        )}
      </div>
      {showRetry && (
        <div className="mt-2">
          {retryHref ? (
            <Button asChild size="sm" variant="default">
              <a href={retryHref}>{retryLabel}</a>
            </Button>
          ) : (
            <Button size="sm" variant="default" onClick={retryOnClick}>
              {retryLabel}
            </Button>
          )}
        </div>
      )}
      {hint && (
        <p className="text-xs text-muted-foreground mt-2 max-w-md">{hint}</p>
      )}
    </div>
  );
}
