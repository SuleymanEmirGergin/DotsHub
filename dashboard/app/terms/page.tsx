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
 * Terms of Service page.
 *
 * Required by App Store / Play Store for submission; also referenced
 * from mobile app (EXPO_PUBLIC_TERMS_URL planned).
 *
 * The medical disclaimer is the MOST IMPORTANT section on the page —
 * Triaige routes users to specialists but does not diagnose. Every
 * revision of this file must preserve or strengthen that language.
 * See config/emergency_rules.json for the complementary hard-stop
 * logic that EMERGENCY envelopes surface in the app itself.
 */
export default async function TermsPage() {
  const locale = await getLocale();
  const t = (key: string) => getText(locale, `terms.${key}`);
  const tList = (key: string) => getTextArray(locale, `terms.${key}`);

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

      <Section title={t("serviceTitle")} body={t("serviceBody")} />

      {/* Medical disclaimer — emphasised with a red-ish accent card.
          Store reviewers read this section specifically; the critical
          paragraph at the end is the text app reviewers flag if
          weakened. */}
      <div
        style={{
          marginBottom: 32,
          padding: 20,
          borderRadius: 12,
          background: "var(--dash-accent-bg)",
          border: "2px solid var(--dash-accent)",
        }}
      >
        <h2
          style={{
            fontSize: 20,
            fontWeight: 800,
            marginBottom: 12,
            color: "var(--dash-text)",
          }}
        >
          {t("medicalDisclaimerTitle")}
        </h2>
        <p style={{ fontSize: 14, marginBottom: 10 }}>
          {t("medicalDisclaimerBody")}
        </p>
        <ul
          style={{
            fontSize: 14,
            paddingLeft: 20,
            marginTop: 0,
            marginBottom: 12,
          }}
        >
          {tList("medicalDisclaimerList").map((item, i) => (
            <li key={i} style={{ marginBottom: 4 }}>
              {item}
            </li>
          ))}
        </ul>
        <p
          style={{
            fontSize: 14,
            fontWeight: 700,
            marginTop: 12,
            padding: 12,
            borderRadius: 8,
            background: "var(--dash-bg)",
            color: "var(--dash-text)",
          }}
        >
          {t("medicalDisclaimerCritical")}
        </p>
      </div>

      <Section title={t("eligibilityTitle")} body={t("eligibilityBody")} />

      <Section title={t("accountTitle")} body={t("accountBody")} />

      <Section
        title={t("acceptableUseTitle")}
        body={t("acceptableUseBody")}
        bullets={tList("acceptableUseList")}
      />

      <Section title={t("intellectualPropertyTitle")} body={t("intellectualPropertyBody")} />

      <Section title={t("liabilityTitle")} body={t("liabilityBody")} />

      <Section title={t("terminationTitle")} body={t("terminationBody")} />

      <Section title={t("changesTitle")} body={t("changesBody")} />

      <Section title={t("governingLawTitle")} body={t("governingLawBody")} />

      <Section title={t("contactTitle")} body={t("contactBody")} />

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
        <Link href="/privacy" style={{ color: "var(--dash-accent)" }}>
          {getText(locale, "nav.privacy")}
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

function Section({
  title,
  body,
  bullets,
}: {
  title: string;
  body: string;
  bullets?: string[];
}) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>{title}</h2>
      <p
        style={{
          fontSize: 14,
          color: "var(--dash-text)",
          marginBottom: bullets?.length ? 10 : 0,
        }}
      >
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
    </section>
  );
}
