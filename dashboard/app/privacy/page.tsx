import { cookies } from "next/headers";
import Link from "next/link";
import { getText, getTextArray } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

/**
 * Privacy policy page — KVKK (Turkey) + GDPR (EU) compliant.
 *
 * Kept as a server component (no client interactivity) so the rendered
 * HTML is fully indexable + cache-able by Vercel's edge. The locale
 * cookie routes which message bundle to pull from.
 *
 * Contact for all privacy-related requests: emirgergin21@gmail.com.
 * Any change to this page title, dates, or i18n structure should be
 * mirrored in the mobile app — the mobile `EXPO_PUBLIC_PRIVACY_URL`
 * env deep-links here, so broken anchors there = broken in store too.
 */
export default async function PrivacyPage() {
  const locale = await getLocale();
  const t = (key: string) => getText(locale, `privacy.${key}`);
  const tList = (key: string) => getTextArray(locale, `privacy.${key}`);

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 760,
        margin: "0 auto",
        background: "var(--dash-bg)",
        color: "var(--dash-text)",
        minHeight: "100vh",
        lineHeight: 1.65,
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

      <h1 style={{ fontSize: 30, fontWeight: 800, margin: "0 0 8px" }}>
        {t("title")}
      </h1>
      <p style={{ color: "var(--dash-text-muted)", fontSize: 13, marginBottom: 24 }}>
        {t("lastUpdated")}
      </p>
      <p style={{ marginBottom: 32 }}>{t("intro")}</p>

      <Section title={t("dataControllerTitle")} body={t("dataControllerBody")} />

      <Section
        title={t("dataCollectedTitle")}
        body={t("dataCollectedBody")}
        bullets={tList("dataCollectedList")}
      />

      <Section title={t("notCollectedTitle")} body={t("notCollectedBody")} />

      <Section title={t("legalBasisTitle")} body={t("legalBasisBody")} />

      <Section
        title={t("purposeTitle")}
        body={t("purposeBody")}
        bullets={tList("purposeList")}
      />

      <Section title={t("storageTitle")} body={t("storageBody")} />

      <Section
        title={t("sharingTitle")}
        body={t("sharingBody")}
        bullets={tList("sharingList")}
      />

      <Section
        title={t("rightsTitle")}
        body={t("rightsBody")}
        bullets={tList("rightsList")}
        footer={t("rightsContact")}
      />

      <Section title={t("securityTitle")} body={t("securityBody")} />

      <Section title={t("childrenTitle")} body={t("childrenBody")} />

      <Section title={t("changesTitle")} body={t("changesBody")} />

      <div
        style={{
          marginTop: 32,
          padding: 16,
          borderRadius: 10,
          background: "var(--dash-accent-bg)",
          border: "1px solid var(--dash-border)",
          fontSize: 13,
          color: "var(--dash-text)",
        }}
      >
        {t("disclaimer")}
      </div>

      <div
        style={{
          marginTop: 40,
          paddingTop: 20,
          borderTop: "1px solid var(--dash-border)",
          fontSize: 12,
          color: "var(--dash-text-muted)",
          display: "flex",
          gap: 16,
        }}
      >
        <Link href="/terms" style={{ color: "var(--dash-accent)" }}>
          {getText(locale, "nav.terms")}
        </Link>
        <span>·</span>
        <a
          href="mailto:emirgergin21@gmail.com"
          style={{ color: "var(--dash-accent)" }}
        >
          emirgergin21@gmail.com
        </a>
      </div>
    </div>
  );
}

/**
 * Consistent section renderer. Body is a paragraph; optional bullets
 * render as a tight <ul>; optional footer is a small italicised note
 * (used for the "how to exercise your rights" contact reminder).
 */
function Section({
  title,
  body,
  bullets,
  footer,
}: {
  title: string;
  body: string;
  bullets?: string[];
  footer?: string;
}) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>{title}</h2>
      <p style={{ fontSize: 14, color: "var(--dash-text)", marginBottom: bullets?.length ? 10 : 0 }}>
        {body}
      </p>
      {bullets && bullets.length > 0 && (
        <ul
          style={{
            fontSize: 14,
            paddingLeft: 20,
            marginTop: 0,
            marginBottom: 0,
            color: "var(--dash-text)",
          }}
        >
          {bullets.map((b, i) => (
            <li key={i} style={{ marginBottom: 4 }}>
              {b}
            </li>
          ))}
        </ul>
      )}
      {footer && (
        <p
          style={{
            fontSize: 13,
            fontStyle: "italic",
            marginTop: 10,
            color: "var(--dash-text-muted)",
          }}
        >
          {footer}
        </p>
      )}
    </section>
  );
}
