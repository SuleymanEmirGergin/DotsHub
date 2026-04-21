import Link from "next/link";
import { cookies } from "next/headers";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

const COOKIE_NAME = "NEXT_LOCALE";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get(COOKIE_NAME)?.value === "en" ? "en" : "tr";
}

export default async function NotFound() {
  const locale = await getLocale();
  const title = getText(locale, "common.notFound");
  const description = getText(locale, "common.notFoundDescription");

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
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>404</h1>
      <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>{title}</h2>
      <p style={{ color: "var(--dash-text-muted, #666)", marginBottom: 24, maxWidth: 400 }}>
        {description}
      </p>
      <Link
        href="/admin/sessions"
        style={{
          padding: "10px 20px",
          borderRadius: 8,
          border: "1px solid var(--dash-border)",
          background: "var(--dash-primary, #1D4ED8)",
          color: "#fff",
          textDecoration: "none",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {getText(locale, "nav.sessions")}
      </Link>
    </div>
  );
}
