"use client";

import { useRouter } from "next/navigation";
import type { Locale } from "@/lib/i18n";

const COOKIE_NAME = "NEXT_LOCALE";
const COOKIE_PATH = "/";

function setLocaleCookie(locale: Locale): void {
  if (typeof document === "undefined") return;
  document.cookie = `${COOKIE_NAME}=${locale};path=${COOKIE_PATH};max-age=31536000`;
}

export function LocaleSwitcher({ initialLocale }: { initialLocale: Locale }) {
  const router = useRouter();

  function switchTo(locale: Locale) {
    if (locale === initialLocale) return;
    setLocaleCookie(locale);
    router.refresh();
  }

  return (
    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <button
        type="button"
        onClick={() => switchTo("tr")}
        aria-pressed={initialLocale === "tr"}
        title="Türkçe"
        style={{
          padding: "6px 10px",
          borderRadius: 8,
          border: "1px solid var(--dash-border)",
          background: initialLocale === "tr" ? "var(--dash-primary, #1D4ED8)" : "var(--dash-bg-card)",
          color: initialLocale === "tr" ? "#fff" : "var(--dash-text)",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        TR
      </button>
      <button
        type="button"
        onClick={() => switchTo("en")}
        aria-pressed={initialLocale === "en"}
        title="English"
        style={{
          padding: "6px 10px",
          borderRadius: 8,
          border: "1px solid var(--dash-border)",
          background: initialLocale === "en" ? "var(--dash-primary, #1D4ED8)" : "var(--dash-bg-card)",
          color: initialLocale === "en" ? "#fff" : "var(--dash-text)",
          cursor: "pointer",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        EN
      </button>
    </span>
  );
}
