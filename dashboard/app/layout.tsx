import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import Script from "next/script";
import { Inter, Source_Serif_4, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeToggle } from "./ThemeToggle";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const sourceSerif4 = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-serif",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "PreTriage Dashboard",
  description: "Doktor triyaj özeti & analitik paneli",
  icons: { icon: "/favicon.svg" },
};

const LOCALE_COOKIE = "NEXT_LOCALE";

function getLocaleFromCookies(cookieStore: Awaited<ReturnType<typeof cookies>>): Locale {
  const value = cookieStore.get(LOCALE_COOKIE)?.value;
  return value === "en" ? "en" : "tr";
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const locale = getLocaleFromCookies(cookieStore);

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${inter.variable} ${sourceSerif4.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-background text-foreground font-sans antialiased">
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(function(){var t=localStorage.getItem("pretriage-dashboard-theme");var d=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";var v=t||d;document.documentElement.setAttribute("data-theme",v);document.documentElement.classList.toggle("dark",v==="dark");})();`,
          }}
        />
        <header className="sticky top-0 z-10 flex justify-end items-center gap-3 py-3 px-6 border-b border-border bg-card">
          <Link
            href="/privacy"
            className="text-sm font-semibold text-muted-foreground no-underline mr-2 hover:text-foreground"
          >
            {getText(locale, "nav.privacy")}
          </Link>
          <LocaleSwitcher initialLocale={locale} />
          <ThemeToggle />
        </header>
        {children}
      </body>
    </html>
  );
}
