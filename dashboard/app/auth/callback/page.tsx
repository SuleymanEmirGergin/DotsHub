"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createBrowserClient } from "@/lib/supabaseBrowser";

/**
 * Auth callback: handles both PKCE (?code=...) and implicit flow (#access_token=...).
 * Hash is only visible in the browser, so we must run on the client.
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const sb = createBrowserClient();

    if (code) {
      sb.auth
        .exchangeCodeForSession(code)
        .then(({ error: err }) => {
          if (err) {
            setError(err.message);
            return;
          }
          router.replace("/admin/sessions");
        })
        .catch((e) => setError(e?.message ?? "Giriş tamamlanamadı."));
      return;
    }

    const hash = typeof window !== "undefined" ? window.location.hash : "";
    if (hash) {
      const params = new URLSearchParams(hash.replace(/^#/, ""));
      const access_token = params.get("access_token");
      const refresh_token = params.get("refresh_token");
      if (access_token && refresh_token) {
        sb.auth
          .setSession({ access_token, refresh_token })
          .then(({ error: err }) => {
            if (err) {
              setError(err.message);
              return;
            }
            router.replace("/admin/sessions");
          })
          .catch((e) => setError(e?.message ?? "Giriş tamamlanamadı."));
        return;
      }
    }

    setError("Giriş linki geçersiz veya eksik. Lütfen yeniden magic link isteyin.");
  }, [searchParams, router]);

  if (error) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          padding: 24,
          background: "var(--dash-bg)",
          color: "var(--dash-text)",
        }}
      >
        <p style={{ color: "#ef4444", textAlign: "center" }}>{error}</p>
        <a
          href="/login"
          style={{
            padding: "12px 24px",
            background: "var(--dash-accent)",
            color: "var(--dash-bg)",
            borderRadius: 12,
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          Giriş sayfasına dön
        </a>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--dash-bg)",
        color: "var(--dash-text-muted)",
      }}
    >
      Giriş tamamlanıyor…
    </div>
  );
}
