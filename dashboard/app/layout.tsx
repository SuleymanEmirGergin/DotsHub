import type { Metadata } from "next";

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
    <html lang="tr">
      <body
        style={{
          margin: 0,
          fontFamily:
            'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          backgroundColor: "#FAFAFA",
          color: "#111",
        }}
      >
        {children}
      </body>
    </html>
  );
}
