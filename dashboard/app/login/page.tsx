"use client";

import { useState } from "react";
import { createClient } from "@supabase/supabase-js";

const sb = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function sendMagicLink() {
    setError("");
    const { error: err } = await sb.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (err) {
      setError(err.message);
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
              disabled={!email.includes("@")}
              style={{
                width: "100%",
                marginTop: 14,
                padding: 14,
                borderRadius: 12,
                border: "none",
                background: "var(--dash-accent)",
                color: "var(--dash-bg)",
                fontSize: 15,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Send magic link
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
