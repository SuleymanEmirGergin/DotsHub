"use client";

import { useEffect } from "react";
import { getText } from "@/lib/i18n";

const COOKIE_NAME = "NEXT_LOCALE";

function getLocaleFromDocument(): "tr" | "en" {
  if (typeof document === "undefined") return "tr";
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_NAME}=([^;]*)`));
  return match?.[1] === "en" ? "en" : "tr";
}

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.error("Admin page error:", error?.message ?? error);
    }
  }, [error]);

  const locale = getLocaleFromDocument();
  const title = getText(locale, "common.errorTitle");
  const retryLabel = getText(locale, "common.retry");

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center">
      <div className="mb-4 rounded-full bg-red-50 p-3">
        <svg
          className="h-6 w-6 text-red-500"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
      </div>
      <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--dash-text-primary)" }}>
        {title}
      </h2>
      <p
        className="mb-6 max-w-sm text-sm"
        style={{ color: "var(--dash-text-muted)" }}
      >
        {error?.message ?? (locale === "tr" ? "Sayfa yüklenirken bir hata oluştu." : "An error occurred while loading the page.")}
      </p>
      <button
        type="button"
        onClick={reset}
        className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
        style={{ background: "var(--dash-primary, #0A84FF)" }}
      >
        {retryLabel}
      </button>
    </div>
  );
}
