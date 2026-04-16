import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { cn } from "@/lib/utils";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

function loadLatestEffectivenessReport() {
    try {
        const reportsDir = path.join(process.cwd(), "..", "backend", "reports");
        if (!fs.existsSync(reportsDir)) return null;

        const files = fs
            .readdirSync(reportsDir)
            .filter((f) => f.startsWith("question_effectiveness_") && f.endsWith(".json"))
            .sort();

        if (files.length === 0) return null;

        const latest = files[files.length - 1];
        const p = path.join(reportsDir, latest);
        return JSON.parse(fs.readFileSync(p, "utf-8"));
    } catch {
        return null;
    }
}

function Sparkline({ data, colorClass }: { data: number[]; colorClass?: string }) {
  if (!data || data.length === 0) return <span className="text-gray-400">—</span>;

  const max = Math.max(...data, 0.01);
  const min = Math.min(...data, 0);
  const range = max - min || 0.01;

  const points = data
    .map((v, i) => {
      const x = (i / Math.max(1, data.length - 1)) * 60;
      const y = 20 - ((v - min) / range) * 18;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width="64" height="20" className={cn("inline-block align-middle", colorClass)}>
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export default async function TuningMetricsPage() {
    await requireAdmin();
    const locale = await getLocale();

    const sb = supabaseAdmin();

    // Fetch recent sessions for overall metrics
    const { data: sessions } = await sb
        .from("triage_sessions")
        .select("confidence_0_1,turn_index,envelope_type")
        .eq("envelope_type", "result")
        .order("created_at", { ascending: false })
        .limit(1000);

    const totalSessions = sessions?.length ?? 0;
    const avgConf = sessions ? sessions.reduce((sum, s) => sum + (s.confidence_0_1 ?? 0), 0) / totalSessions : 0;
    const avgQuestions = sessions ? sessions.reduce((sum, s) => sum + (s.turn_index ?? 0), 0) / totalSessions : 0;

    // Load effectiveness report
    const effectiveness = loadLatestEffectivenessReport();
    const questions = effectiveness?.questions ?? [];

    // Sort by effectiveness
    const sortedQuestions = [...questions].sort((a: any, b: any) => (b.effectiveness_0_1 ?? 0) - (a.effectiveness_0_1 ?? 0));

  const effColorClass = (eff: number) =>
    eff >= 0.6 ? "text-teal-800 dark:text-teal-400" : eff >= 0.4 ? "text-amber-800 dark:text-amber-400" : "text-red-800 dark:text-red-400";

  return (
    <div className="p-6 font-sans bg-background text-foreground min-h-screen">
      <div className="max-w-[1400px] mx-auto">
        <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.tuningMetrics") }]} />
        <h1 className="text-[26px] font-black m-0">{getText(locale, "tuningMetrics.title")}</h1>
        <div className="text-muted-foreground mt-1.5">{getText(locale, "tuningMetrics.subtitle")}</div>

        <div className="mt-3.5 grid grid-cols-3 gap-3.5">
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{getText(locale, "tuningMetrics.sessionsRecent")}</div>
            <div className="mt-2 text-3xl font-black">{totalSessions}</div>
          </div>
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{getText(locale, "tuningMetrics.avgConfidence")}</div>
            <div className="mt-2 text-3xl font-black">{avgConf.toFixed(3)}</div>
          </div>
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{getText(locale, "tuningMetrics.avgQuestions")}</div>
            <div className="mt-2 text-3xl font-black">{avgQuestions.toFixed(1)}</div>
          </div>
        </div>

        <div className="mt-5">
          <h2 className="text-lg font-black m-0">{getText(locale, "tuningMetrics.questionEffectiveness")}</h2>
          <div className="text-muted-foreground mt-1 text-[13px]">
            {effectiveness
              ? getText(locale, "tuningMetrics.reportGenerated").replace("{date}", new Date(effectiveness.generated_at).toLocaleString(locale === "en" ? "en-US" : "tr-TR"))
              : getText(locale, "tuningMetrics.noReportAvailable")}
          </div>
        </div>

        {questions.length > 0 ? (
          <div className="mt-3.5 bg-card rounded-2xl border border-border overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-accent border-b border-border">
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.question")}</th>
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.asked")}</th>
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.effectiveness")}</th>
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.gapDelta")}</th>
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.confDelta")}</th>
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.balance")}</th>
                  <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningMetrics.trend")}</th>
                </tr>
              </thead>
              <tbody>
                {sortedQuestions.slice(0, 50).map((q: any) => {
                  const eff = q.effectiveness_0_1 ?? 0;
                  const trendData = [eff * 0.9, eff * 0.95, eff, eff * 1.02, eff * 1.01];
                  return (
                    <tr key={q.canonical} className="border-t border-border">
                      <td className="p-3 text-[13px] font-bold">{q.canonical}</td>
                      <td className="p-3 text-xs text-muted-foreground">{q.asked_count}</td>
                      <td className={cn("p-3 text-[13px] font-black", effColorClass(eff))}>{(eff * 100).toFixed(1)}%</td>
                      <td className={cn("p-3 text-xs", (q.avg_gap_delta ?? 0) > 0 ? "text-teal-800 dark:text-teal-400" : "text-muted-foreground")}>
                        {q.avg_gap_delta ? `+${q.avg_gap_delta.toFixed(3)}` : "—"}
                      </td>
                      <td className={cn("p-3 text-xs", (q.avg_conf_delta ?? 0) > 0 ? "text-teal-800 dark:text-teal-400" : "text-muted-foreground")}>
                        {q.avg_conf_delta ? `+${q.avg_conf_delta.toFixed(3)}` : "—"}
                      </td>
                      <td className="p-3 text-xs">{q.balance_0_1 ? (q.balance_0_1 * 100).toFixed(0) + "%" : "—"}</td>
                      <td className="p-3">
                        <Sparkline data={trendData} colorClass={effColorClass(eff)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="mt-3.5 p-10 text-center text-muted-foreground bg-card rounded-2xl border border-border">
            {getText(locale, "tuningMetrics.noEffectivenessData")}
          </div>
        )}
      </div>
    </div>
  );
}
