import { cookies } from "next/headers";
import Link from "next/link";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

export default async function PrivacyPage() {
  const locale = await getLocale();

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 640,
        margin: "0 auto",
        background: "var(--dash-bg)",
        color: "var(--dash-text)",
        minHeight: "100vh",
      }}
    >
      <Link
        href="/"
        style={{
          display: "inline-block",
          marginBottom: 24,
          color: "var(--dash-accent)",
          textDecoration: "none",
          fontWeight: 600,
          fontSize: 14,
        }}
      >
        ← {getText(locale, "common.back")}
      </Link>
      <h1 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 16px" }}>
        {getText(locale, "privacy.title")}
      </h1>
      <p style={{ color: "var(--dash-text-muted)", marginBottom: 24 }}>
        {getText(locale, "privacy.intro")}
      </p>
      <section style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{getText(locale, "privacy.dataCollectedTitle")}</h2>
        <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--dash-text)" }}>
          {getText(locale, "privacy.dataCollected")}
        </p>
      </section>
      <section style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{getText(locale, "privacy.storageTitle")}</h2>
        <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--dash-text)" }}>
          {getText(locale, "privacy.storage")}
        </p>
      </section>
      <section style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>{getText(locale, "privacy.rightsTitle")}</h2>
        <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--dash-text)" }}>
          {getText(locale, "privacy.rights")}
        </p>
      </section>
      <p style={{ fontSize: 12, color: "var(--dash-text-muted)", marginTop: 24 }}>
        {getText(locale, "privacy.disclaimer")}
      </p>
    </div>
  );
}
