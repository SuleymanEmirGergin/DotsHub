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
        backgroundColor: "#fafafa",
      }}
    >
      <div
        style={{
          backgroundColor: "#fff",
          borderRadius: 20,
          padding: 40,
          maxWidth: 400,
          width: "100%",
          boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 6 }}>
          Admin Login
        </h1>
        <p style={{ color: "#666", fontSize: 14, marginBottom: 24 }}>
          PreTriage Dashboard
        </p>

        {sent ? (
          <div
            style={{
              padding: 20,
              borderRadius: 12,
              backgroundColor: "#E8F5E9",
              color: "#2E7D32",
              textAlign: "center",
              fontWeight: 600,
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
                border: "1px solid #ddd",
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
                backgroundColor: "#111",
                color: "#fff",
                fontSize: 15,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Send magic link
            </button>
            {error && (
              <p style={{ color: "#C62828", marginTop: 12, fontSize: 13 }}>
                {error}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
