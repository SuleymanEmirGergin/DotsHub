import { cookies } from "next/headers";
import Link from "next/link";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

/**
 * Public landing page at /.
 *
 * Previously this file did `redirect("/admin/sessions")` which was
 * fine internally but meant store reviewers landing here saw an
 * auth wall with no brand context. This page replaces the redirect
 * with a minimal marketing surface:
 *   - Hero (name + tagline + sub)
 *   - 3-step "how it works"
 *   - Safety disclaimer (medical-disclaimer-forward, required by
 *     Apple/Google submission review)
 *   - CTA to app + privacy/terms + admin login + contact
 *
 * Admin dashboard stays fully functional — the "Admin Login" link
 * in the top-right + bottom footer routes to /login as before.
 *
 * i18n: tr + en, cookie-driven locale (same pattern as privacy +
 * terms pages). Server component so rendered HTML is cache-able at
 * Vercel's edge — fast first paint for anonymous visitors.
 */
export default async function HomePage() {
  const locale = await getLocale();
  const t = (key: string) => getText(locale, `landing.${key}`);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--dash-bg)",
        color: "var(--dash-text)",
      }}
    >
      {/* ───── Top bar ───── */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "20px 24px",
          maxWidth: 1080,
          margin: "0 auto",
          borderBottom: "1px solid var(--dash-border)",
        }}
      >
        <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: -0.5 }}>
          {t("heroTitle")}
        </div>
        <nav style={{ display: "flex", gap: 18, fontSize: 14 }}>
          <Link
            href="/privacy"
            style={{ color: "var(--dash-text-muted)", textDecoration: "none" }}
          >
            {getText(locale, "nav.privacy")}
          </Link>
          <Link
            href="/terms"
            style={{ color: "var(--dash-text-muted)", textDecoration: "none" }}
          >
            {getText(locale, "nav.terms")}
          </Link>
          <Link
            href="/login"
            style={{
              color: "var(--dash-accent)",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            {getText(locale, "nav.adminEntry")}
          </Link>
        </nav>
      </header>

      {/* ───── Hero ───── */}
      <section
        style={{
          padding: "80px 24px 60px",
          maxWidth: 760,
          margin: "0 auto",
          textAlign: "center",
        }}
      >
        <h1
          style={{
            fontSize: 52,
            fontWeight: 900,
            letterSpacing: -1.2,
            margin: "0 0 20px",
            lineHeight: 1.1,
          }}
        >
          {t("heroTagline")}
        </h1>
        <p
          style={{
            fontSize: 18,
            color: "var(--dash-text-muted)",
            lineHeight: 1.55,
            margin: "0 0 32px",
          }}
        >
          {t("heroSub")}
        </p>
        <div
          style={{
            display: "flex",
            gap: 12,
            justifyContent: "center",
            flexWrap: "wrap",
          }}
        >
          <a
            href="#how-it-works"
            style={{
              padding: "14px 28px",
              borderRadius: 12,
              background: "var(--dash-accent)",
              color: "var(--dash-bg)",
              textDecoration: "none",
              fontWeight: 700,
              fontSize: 15,
            }}
          >
            {t("ctaLearnMore")}
          </a>
          <a
            href="#download"
            style={{
              padding: "14px 28px",
              borderRadius: 12,
              background: "transparent",
              color: "var(--dash-text)",
              textDecoration: "none",
              fontWeight: 600,
              fontSize: 15,
              border: "1px solid var(--dash-border)",
            }}
          >
            {t("ctaTryApp")}
          </a>
        </div>
      </section>

      {/* ───── How it works (3 steps) ───── */}
      <section
        id="how-it-works"
        style={{
          padding: "60px 24px 80px",
          maxWidth: 960,
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 24,
          }}
        >
          <StepCard title={t("step1Title")} body={t("step1Body")} icon="💬" />
          <StepCard title={t("step2Title")} body={t("step2Body")} icon="🩺" />
          <StepCard title={t("step3Title")} body={t("step3Body")} icon="✅" />
        </div>
      </section>

      {/* ───── Safety disclaimer ───── */}
      <section style={{ padding: "40px 24px 80px", maxWidth: 760, margin: "0 auto" }}>
        <div
          style={{
            padding: 28,
            borderRadius: 16,
            background: "var(--dash-accent-bg)",
            border: "2px solid var(--dash-accent)",
          }}
        >
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: "0 0 12px" }}>
            🚨 {t("safetyTitle")}
          </h2>
          <p style={{ fontSize: 15, lineHeight: 1.6, margin: 0, color: "var(--dash-text)" }}>
            {t("safetyBody")}
          </p>
        </div>
      </section>

      {/* ───── CTA — store coming soon ───── */}
      <section
        id="download"
        style={{
          padding: "40px 24px 100px",
          maxWidth: 760,
          margin: "0 auto",
          textAlign: "center",
        }}
      >
        <h2 style={{ fontSize: 28, fontWeight: 800, margin: "0 0 12px" }}>
          {t("ctaDownload")}
        </h2>
        <p style={{ fontSize: 15, color: "var(--dash-text-muted)", margin: "0 0 24px" }}>
          {t("storesComingSoon")}
        </p>
        {/* Store badges placeholder — slot in real links when iOS
            TestFlight / Play internal distribution go live. Keeping
            the CTA visible now sets expectation for submission
            reviewers visiting the landing page. */}
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <div
            style={{
              padding: "14px 24px",
              borderRadius: 12,
              background: "var(--dash-bg-card, var(--dash-bg))",
              border: "1px solid var(--dash-border)",
              color: "var(--dash-text-muted)",
              fontSize: 14,
              fontStyle: "italic",
            }}
          >
            📱 App Store — {locale === "tr" ? "yakında" : "soon"}
          </div>
          <div
            style={{
              padding: "14px 24px",
              borderRadius: 12,
              background: "var(--dash-bg-card, var(--dash-bg))",
              border: "1px solid var(--dash-border)",
              color: "var(--dash-text-muted)",
              fontSize: 14,
              fontStyle: "italic",
            }}
          >
            🤖 Google Play — {locale === "tr" ? "yakında" : "soon"}
          </div>
        </div>
      </section>

      {/* ───── Footer ───── */}
      <footer
        style={{
          borderTop: "1px solid var(--dash-border)",
          padding: "32px 24px",
          maxWidth: 1080,
          margin: "0 auto",
          fontSize: 13,
          color: "var(--dash-text-muted)",
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>{t("footerBuiltBy")}</div>
        <div style={{ display: "flex", gap: 16 }}>
          <Link
            href="/privacy"
            style={{ color: "var(--dash-text-muted)", textDecoration: "none" }}
          >
            {getText(locale, "nav.privacy")}
          </Link>
          <Link
            href="/terms"
            style={{ color: "var(--dash-text-muted)", textDecoration: "none" }}
          >
            {getText(locale, "nav.terms")}
          </Link>
          <a
            href="mailto:emirgergin21@gmail.com"
            style={{ color: "var(--dash-text-muted)", textDecoration: "none" }}
          >
            {t("footerContact")}
          </a>
        </div>
      </footer>
    </div>
  );
}

function StepCard({ title, body, icon }: { title: string; body: string; icon: string }) {
  return (
    <div
      style={{
        padding: 28,
        borderRadius: 16,
        background: "var(--dash-bg-card, var(--dash-bg))",
        border: "1px solid var(--dash-border)",
        color: "var(--dash-text)",
      }}
    >
      <div style={{ fontSize: 40, marginBottom: 12, lineHeight: 1 }}>{icon}</div>
      <h3 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 8px", color: "var(--dash-text)" }}>
        {title}
      </h3>
      <p style={{ fontSize: 14, lineHeight: 1.55, margin: 0, color: "var(--dash-text-muted)" }}>
        {body}
      </p>
    </div>
  );
}
