"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
// IMPORTANT: use the same `@supabase/ssr` cookie-backed client as
// app/auth/callback/page.tsx — otherwise the PKCE code_verifier
// stored here (localStorage) won't be found by exchangeCodeForSession
// on the callback side, which reads from cookies. That mismatch was
// the root cause of staging e2e auth tests failing 4/4 runs
// (post-mortem in docs/OPS_STAGING_SETUP.md isteyen olursa).
import { createBrowserClient } from "@/lib/supabaseBrowser";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
const isSupabaseConfigured =
  supabaseUrl.length > 0 &&
  !supabaseUrl.includes("xxxx") &&
  supabaseAnonKey.length > 0 &&
  supabaseAnonKey !== "your_anon_key";

// Falls back to null when env isn't set so the UI can render a helpful
// "configure env" message instead of crashing on the non-null assertion
// inside createBrowserClient().
const sb = isSupabaseConfigured ? createBrowserClient() : null;

const RATE_LIMIT_COOLDOWN_SEC = 60;

function LoginForm() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [cooldownSec, setCooldownSec] = useState(0);

  useEffect(() => {
    const err = searchParams.get("error");
    const msg = searchParams.get("message");
    if (err === "callback" && msg) {
      setError(decodeURIComponent(msg));
    } else if (err === "missing_code") {
      setError("Giriş linki geçersiz veya eksik. Lütfen yeniden magic link isteyin.");
    }
  }, [searchParams]);

  useEffect(() => {
    if (cooldownSec <= 0) return;
    const t = setInterval(() => setCooldownSec((s) => (s <= 1 ? 0 : s - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldownSec]);

  async function sendMagicLink() {
    setError("");
    if (!sb) {
      setError(
        "Supabase yapılandırılmamış. Giriş için dashboard/.env.local içinde NEXT_PUBLIC_SUPABASE_URL ve NEXT_PUBLIC_SUPABASE_ANON_KEY değerlerini gerçek Supabase projenizden alıp ayarlayın."
      );
      return;
    }
    const { error: err } = await sb.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (err) {
      const isRateLimit =
        err.message?.toLowerCase().includes("rate limit") ||
        err.message?.toLowerCase().includes("too many");
      if (isRateLimit) {
        setError("Çok fazla deneme. Birkaç dakika sonra tekrar deneyin.");
        setCooldownSec(RATE_LIMIT_COOLDOWN_SEC);
      } else {
        setError(err.message);
      }
    } else {
      setSent(true);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--dash-bg)",
      }}
    >
      <div
        style={{
          background: "var(--dash-bg-card)",
          borderRadius: 20,
          padding: 40,
          maxWidth: 400,
          width: "100%",
          boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
          border: "1px solid var(--dash-border)",
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 6, color: "var(--dash-text)" }}>
          Admin Login
        </h1>
        <p style={{ color: "var(--dash-text-muted)", fontSize: 14, marginBottom: 24 }}>
          PreTriage Dashboard
        </p>

        {!isSupabaseConfigured && (
          <div
            style={{
              padding: 14,
              marginBottom: 20,
              borderRadius: 12,
              background: "var(--dash-accent-bg)",
              color: "var(--dash-text-muted)",
              fontSize: 13,
              border: "1px solid var(--dash-border)",
            }}
          >
            Supabase yapılandırılmamış. Magic link ile giriş için <code>.env.local</code> içinde{" "}
            <code>NEXT_PUBLIC_SUPABASE_URL</code> ve <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> değerlerini gerçek Supabase projenizden ayarlayın.
          </div>
        )}

        {sent ? (
          <div
            style={{
              padding: 20,
              borderRadius: 12,
              background: "var(--dash-accent-bg)",
              color: "var(--dash-text)",
              textAlign: "center",
              fontWeight: 600,
              border: "1px solid var(--dash-border)",
            }}
          >
            Magic link gönderildi! E-postanı kontrol et.
          </div>
        ) : (
          <>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
              onKeyDown={(e) => e.key === "Enter" && sendMagicLink()}
              style={{
                width: "100%",
                padding: 14,
                borderRadius: 12,
                border: "1px solid var(--dash-border)",
                background: "var(--dash-bg)",
                color: "var(--dash-text)",
                fontSize: 15,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
            <button
              onClick={sendMagicLink}
              disabled={!email.includes("@") || !isSupabaseConfigured || cooldownSec > 0}
              style={{
                width: "100%",
                marginTop: 14,
                padding: 14,
                borderRadius: 12,
                border: "none",
                background: cooldownSec > 0 ? "var(--dash-border)" : "var(--dash-accent)",
                color: "var(--dash-bg)",
                fontSize: 15,
                fontWeight: 700,
                cursor: cooldownSec > 0 ? "not-allowed" : "pointer",
              }}
            >
              {cooldownSec > 0
                ? `${cooldownSec} saniye sonra tekrar deneyin`
                : "Send magic link"}
            </button>
            {error && (
              <p style={{ color: "#ef4444", marginTop: 12, fontSize: 13 }}>
                {error}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>Yükleniyor...</div>}>
      <LoginForm />
    </Suspense>
  );
}
