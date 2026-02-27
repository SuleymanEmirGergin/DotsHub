import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { ThemeToggle } from "./ThemeToggle";

export const metadata: Metadata = {
  title: "PreTriage Dashboard",
  description: "Doktor triyaj özeti & analitik paneli",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body
        style={{
          margin: 0,
          fontFamily:
            'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          background: "var(--dash-bg)",
          color: "var(--dash-text)",
        }}
      >
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(function(){var t=localStorage.getItem("pretriage-dashboard-theme");var d=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.setAttribute("data-theme",t||d);})();`,
          }}
        />
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 10,
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            padding: "12px 24px",
            borderBottom: "1px solid var(--dash-border)",
            background: "var(--dash-bg-card)",
          }}
        >
          <ThemeToggle />
        </header>
        {children}
      </body>
    </html>
  );
}
