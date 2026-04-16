import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { StatusAutoRefresh } from "./StatusAutoRefresh";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import type { StatsOverview } from "@/lib/types/admin";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

type Status = "ok" | "warn" | "crit" | "info" | "error";

function formatText(template: string, params: Record<string, string | number>): string {
  let out = template;
  for (const [key, value] of Object.entries(params)) {
    out = out.replaceAll(`{${key}}`, String(value));
  }
  return out;
}

async function checkBackendHealth(t: (key: string) => string): Promise<{ status: Status; message: string }> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return { status: "error", message: t("status.apiBaseNotSet") };
  try {
    const r = await fetch(`${base.replace(/\/+$/, "")}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (r.ok) return { status: "ok", message: t("status.connected") };
    return { status: "error", message: `HTTP ${r.status}` };
  } catch (e: unknown) {
    return { status: "error", message: e instanceof Error ? e.message : t("status.connectionFailed") };
  }
}

async function checkSupabase(t: (key: string) => string): Promise<{ status: Status; message: string }> {
  try {
    const sb = supabaseAdmin();
    const { error } = await sb.from("triage_sessions").select("id").limit(1).maybeSingle();
    if (error) return { status: "error", message: error.message };
    return { status: "ok", message: t("status.connected") };
  } catch (e: unknown) {
    return { status: "error", message: e instanceof Error ? e.message : t("status.connectionFailed") };
  }
}

async function checkAdminOverview(t: (key: string) => string): Promise<{ status: Status; message: string; health?: StatsOverview["health"] }> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) return { status: "info", message: t("status.apiBaseOrKeyMissing") };
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
    return { status, message: formatText(t("status.sessionsState"), { samples, overall }), health: h };
  } catch (e: unknown) {
    return { status: "error", message: e instanceof Error ? e.message : t("status.connectionFailed") };
  }
}

export default async function StatusPage() {
  await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);

  const [backend, supabase, overview] = await Promise.all([
    checkBackendHealth(t),
    checkSupabase(t),
    checkAdminOverview(t),
  ]);

  const statusBadgeClass: Record<Status, string> = {
    ok: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
    warn: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    crit: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    info: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
    error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  };

  const statusLabels: Record<Status, string> = {
    ok: t("status.okLabel"),
    warn: t("status.warnLabel"),
    crit: t("status.criticalLabel"),
    info: t("status.infoLabel"),
    error: t("status.errorLabel"),
  };

  const cards = [
    { title: getText(locale, "status.backendApi"), ...backend },
    { title: getText(locale, "status.supabase"), ...supabase },
    { title: getText(locale, "status.adminStats"), ...overview },
  ];

  return (
    <StatusAutoRefresh>
      <div className="p-6 max-w-[800px] mx-auto bg-background text-foreground min-h-screen">
        <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "status.title") }]} />
        <h1 className="text-[26px] font-black m-0">{getText(locale, "status.title")}</h1>
        <p className="text-muted-foreground mt-2 mb-1">{getText(locale, "status.subtitle")}</p>
        <p className="text-muted-foreground text-xs mb-4">{getText(locale, "status.autoRefreshNote")}</p>
        <div className="mb-6">
          <Button variant="outline" size="sm" asChild>
            <Link href="/admin/sessions">{getText(locale, "nav.sessions")}</Link>
          </Button>
        </div>
        <div className="flex flex-col gap-4">
          {cards.map((card) => (
            <Card key={card.title}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-lg">{card.title}</CardTitle>
                <span
                  className={cn(
                    "py-1 px-2.5 rounded-full text-xs font-bold",
                    statusBadgeClass[card.status]
                  )}
                >
                  {statusLabels[card.status]}
                </span>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground text-sm mb-0">{card.message}</p>
                {card.health && (
                  <div className="mt-3 text-[13px] text-muted-foreground">
                    {getText(locale, "status.sample")}: {card.health.samples} | {getText(locale, "status.lowConf")}: %{(card.health.low_conf_rate * 100).toFixed(1)} | {getText(locale, "status.highRisk")}: %{(card.health.high_risk_rate * 100).toFixed(1)}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </StatusAutoRefresh>
  );
}
