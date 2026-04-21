"use client";

import { useEffect } from "react";
import { getText } from "@/lib/i18n";

const COOKIE_NAME = "NEXT_LOCALE";

function getLocaleFromDocument(): "tr" | "en" {
  if (typeof document === "undefined") return "tr";
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_NAME}=([^;]*)`));
  return match?.[1] === "en" ? "en" : "tr";
}

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.error("Dashboard error boundary:", error?.message ?? error);
    }
  }, [error]);

  const locale = getLocaleFromDocument();
  const title = getText(locale, "common.errorTitle");
  const retryLabel = getText(locale, "common.retry");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        padding: 24,
        textAlign: "center",
      }}
    >
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>{title}</h2>
      <p style={{ color: "var(--dash-text-muted, #666)", marginBottom: 24, maxWidth: 400 }}>
        {error?.message ?? "Something went wrong."}
      </p>
      <button
        type="button"
        onClick={reset}
        style={{
          padding: "10px 20px",
          borderRadius: 8,
          border: "1px solid var(--dash-border)",
          background: "var(--dash-primary, #1D4ED8)",
          color: "#fff",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {retryLabel}
      </button>
    </div>
  );
}
