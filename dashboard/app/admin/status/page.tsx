import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import Link from "next/link";
import { StatusAutoRefresh } from "./StatusAutoRefresh";
import { Breadcrumb } from "@/app/components/Breadcrumb";

export const dynamic = "force-dynamic";

type Status = "ok" | "warn" | "crit" | "info" | "error";

async function checkBackendHealth(): Promise<{ status: Status; message: string }> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return { status: "error", message: "NEXT_PUBLIC_API_BASE not set" };
  try {
    const r = await fetch(`${base.replace(/\/+$/, "")}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (r.ok) return { status: "ok", message: "Bağlı" };
    return { status: "error", message: `HTTP ${r.status}` };
  } catch (e: any) {
    return { status: "error", message: e?.message ?? "Bağlanamadı" };
  }
}

async function checkSupabase(): Promise<{ status: Status; message: string }> {
  try {
    const sb = supabaseAdmin();
    const { error } = await sb.from("triage_sessions").select("id").limit(1).maybeSingle();
    if (error) return { status: "error", message: error.message };
    return { status: "ok", message: "Bağlı" };
  } catch (e: any) {
    return { status: "error", message: e?.message ?? "Bağlanamadı" };
  }
}

async function checkAdminOverview(): Promise<{ status: Status; message: string; health?: any }> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) return { status: "info", message: "API base veya key yok" };
  try {
    const r = await fetch(`${base.replace(/\/+$/, "")}/admin/stats/overview?lookback_limit=100`, {
      headers: { "x-admin-key": key },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) return { status: "error", message: `HTTP ${r.status}` };
    const data = await r.json();
    const h = data?.health;
    const overall = h?.overall ?? "OK";
    const status: Status = overall === "CRIT" ? "crit" : overall === "WARN" ? "warn" : "ok";
    const samples = h?.samples ?? 0;
    return { status, message: `${samples} oturum, durum: ${overall}`, health: h };
  } catch (e: any) {
    return { status: "error", message: e?.message ?? "Bağlanamadı" };
  }
}

const statusStyles: Record<Status, { bg: string; text: string; label: string }> = {
  ok: { bg: "#dcfce7", text: "#166534", label: "OK" },
  warn: { bg: "#fef3c7", text: "#92400e", label: "UYARI" },
  crit: { bg: "#fee2e2", text: "#991b1b", label: "KRİTİK" },
  info: { bg: "#e0e7ff", text: "#3730a3", label: "BİLGİ" },
  error: { bg: "#fee2e2", text: "#991b1b", label: "HATA" },
};

export default async function StatusPage() {
  await requireAdmin();

  const [backend, supabase, overview] = await Promise.all([
    checkBackendHealth(),
    checkSupabase(),
    checkAdminOverview(),
  ]);

  const cards = [
    { title: "Backend API", ...backend },
    { title: "Supabase", ...supabase },
    { title: "Admin + İstatistik", ...overview },
  ];

  return (
    <StatusAutoRefresh>
      <div
        style={{
          padding: 24,
          maxWidth: 800,
          margin: "0 auto",
          background: "var(--dash-bg)",
          color: "var(--dash-text)",
          minHeight: "100vh",
        }}
      >
        <Breadcrumb items={[{ label: "Admin", href: "/admin/sessions" }, { label: "Sistem durumu" }]} />
        <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Sistem durumu</h1>
        <p style={{ color: "var(--dash-text-muted)", marginTop: 8, marginBottom: 4 }}>
          Backend, veritabanı ve admin API durumu
        </p>
        <p style={{ color: "var(--dash-text-muted)", fontSize: 12, marginBottom: 24 }}>
          30 saniyede bir otomatik yenilenir
        </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {cards.map((c) => {
          const style = statusStyles[c.status];
          return (
            <div
              key={c.title}
              style={{
                padding: 20,
                borderRadius: 12,
                border: "1px solid var(--dash-border)",
                background: "var(--dash-bg-card)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 700, fontSize: 18 }}>{c.title}</span>
                <span
                  style={{
                    padding: "4px 10px",
                    borderRadius: 999,
                    background: style.bg,
                    color: style.text,
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                >
                  {style.label}
                </span>
              </div>
              <p style={{ margin: "8px 0 0", color: "var(--dash-text-muted)", fontSize: 14 }}>
                {c.message}
              </p>
              {c.health && (
                <div style={{ marginTop: 12, fontSize: 13, color: "var(--dash-text-muted)" }}>
                  Örnek: {c.health.samples} · Düşük güven: %{(c.health.low_conf_rate * 100).toFixed(1)} · Yüksek risk: %{(c.health.high_risk_rate * 100).toFixed(1)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
    </StatusAutoRefresh>
  );
}
