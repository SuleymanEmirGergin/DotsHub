import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border rounded-2xl p-5 bg-card text-card-foreground">
      <div className="text-[13px] text-muted-foreground mb-3 font-semibold">{title}</div>
      {children}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="p-4 rounded-xl border border-border bg-card text-card-foreground">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-[28px] font-extrabold mt-1">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

function getConfidenceClass(label: string): string {
  const normalized = label.toLowerCase();
  if (normalized.includes("high") || normalized.includes("yuksek") || normalized.includes("yüksek")) return "text-green-700 dark:text-green-400";
  if (normalized.includes("medium") || normalized.includes("orta")) return "text-amber-700 dark:text-amber-400";
  return "text-red-700 dark:text-red-400";
}

export default async function AnalyticsPage() {
  await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);
  const unknown = t("analytics.unknown");

  const sb = supabaseAdmin();

  const { count: totalSessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true });

  const { count: resultSessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "RESULT");

  const { count: emergencySessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "EMERGENCY");

  const { count: sameDaySessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "SAME_DAY");

  const { count: questionSessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "QUESTION");

  const { count: errorSessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "ERROR");

  const totalForDistribution = (totalSessions ?? 0);
  const envelopeDistribution: { type: string; count: number; pct: number }[] = [
    { type: "RESULT", count: resultSessions ?? 0, pct: totalForDistribution ? ((resultSessions ?? 0) / totalForDistribution) * 100 : 0 },
    { type: "EMERGENCY", count: emergencySessions ?? 0, pct: totalForDistribution ? ((emergencySessions ?? 0) / totalForDistribution) * 100 : 0 },
    { type: "SAME_DAY", count: sameDaySessions ?? 0, pct: totalForDistribution ? ((sameDaySessions ?? 0) / totalForDistribution) * 100 : 0 },
    { type: "QUESTION", count: questionSessions ?? 0, pct: totalForDistribution ? ((questionSessions ?? 0) / totalForDistribution) * 100 : 0 },
    { type: "ERROR", count: errorSessions ?? 0, pct: totalForDistribution ? ((errorSessions ?? 0) / totalForDistribution) * 100 : 0 },
  ].filter((r) => r.count > 0);

  const { count: fbUpCount } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .eq("rating", "up");

  const { count: fbDownCount } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .eq("rating", "down");

  const { data: specDist } = await sb
    .from("triage_sessions")
    .select("recommended_specialty_tr")
    .eq("envelope_type", "RESULT")
    .not("recommended_specialty_tr", "is", null)
    .order("created_at", { ascending: false })
    .limit(500);

  const specCounts: Record<string, number> = {};
  (specDist ?? []).forEach((s: any) => {
    const name = s.recommended_specialty_tr || unknown;
    specCounts[name] = (specCounts[name] || 0) + 1;
  });
  const specRanked = Object.entries(specCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const { data: confDist } = await sb
    .from("triage_sessions")
    .select("confidence_label_tr")
    .eq("envelope_type", "RESULT")
    .not("confidence_label_tr", "is", null)
    .limit(500);

  const confCounts: Record<string, number> = {};
  (confDist ?? []).forEach((s: any) => {
    const label = s.confidence_label_tr || unknown;
    confCounts[label] = (confCounts[label] || 0) + 1;
  });

  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const { data: dailySessions } = await sb
    .from("triage_sessions")
    .select("created_at")
    .gte("created_at", sevenDaysAgo.toISOString());

  const dailyCounts: Record<string, number> = {};
  (dailySessions ?? []).forEach((s: any) => {
    const day = new Date(s.created_at).toISOString().slice(0, 10);
    dailyCounts[day] = (dailyCounts[day] || 0) + 1;
  });
  const dailyRanked = Object.entries(dailyCounts).sort((a, b) => a[0].localeCompare(b[0]));

  const { data: confusionRaw } = await sb
    .from("triage_feedback")
    .select("session_id,rating,user_selected_specialty_id")
    .eq("rating", "down")
    .not("user_selected_specialty_id", "is", null)
    .order("created_at", { ascending: false })
    .limit(200);

  const confusionSessionIds = (confusionRaw ?? []).map((f: any) => f.session_id);
  let confusionRows: { predicted: string; actual: string; cnt: number }[] = [];

  if (confusionSessionIds.length > 0) {
    const { data: confSessions } = await sb
      .from("triage_sessions")
      .select("id,recommended_specialty_tr")
      .in("id", confusionSessionIds.slice(0, 100));

    const sessionSpec: Record<string, string> = {};
    (confSessions ?? []).forEach((s: any) => {
      sessionSpec[s.id] = s.recommended_specialty_tr ?? unknown;
    });

    const confPairs: Record<string, number> = {};
    (confusionRaw ?? []).forEach((f: any) => {
      const predicted = sessionSpec[f.session_id] ?? unknown;
      const actual = f.user_selected_specialty_id ?? unknown;
      const key = `${predicted}|||${actual}`;
      confPairs[key] = (confPairs[key] || 0) + 1;
    });

    confusionRows = Object.entries(confPairs)
      .map(([key, cnt]) => {
        const [predicted, actual] = key.split("|||");
        return { predicted, actual, cnt };
      })
      .sort((a, b) => b.cnt - a.cnt);
  }

  const barColor: Record<string, string> = {
    EMERGENCY: "bg-red-600",
    RESULT: "bg-green-700",
    SAME_DAY: "bg-amber-600",
    QUESTION: "bg-blue-700",
    ERROR: "bg-gray-500",
  };

  return (
    <div className="p-6 max-w-[1200px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: t("analytics.title") }]} />
      <div className="flex justify-between items-center">
        <h1 className="text-[26px] font-black m-0">{t("analytics.title")}</h1>
        <div className="flex gap-3">
          <a href="/admin/live" className="font-bold text-emerald-600 no-underline text-[13px] hover:underline">
            {t("analytics.liveLink")} &rarr;
          </a>
          <a href="/admin/feedback" className="font-bold text-primary no-underline text-[13px] hover:underline">
            {t("analytics.feedbackLink")} &rarr;
          </a>
          <a href="/admin/sessions" className="font-bold text-primary no-underline text-[13px] hover:underline">
            {t("analytics.sessionsLink")} &rarr;
          </a>
          <a href="/admin/tuning-report" className="font-bold text-primary no-underline text-[13px] hover:underline">
            {t("analytics.tuningLink")} &rarr;
          </a>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mt-5">
        <Stat label={t("analytics.totalSessions")} value={totalSessions ?? 0} />
        <Stat label={t("analytics.result")} value={resultSessions ?? 0} />
        <Stat label={t("analytics.emergency")} value={emergencySessions ?? 0} />
        <Stat label={t("analytics.feedback")} value={`${fbUpCount ?? 0} / ${fbDownCount ?? 0}`} sub={t("analytics.feedbackSub")} />
      </div>

      {envelopeDistribution.length > 0 && (
        <div className="mt-5">
          <Card title={t("analytics.resultTypeDistribution")}>
            <div className="flex flex-col gap-2.5">
              {envelopeDistribution.map(({ type, count, pct }) => (
                <div key={type} className="flex flex-col gap-1">
                  <div className="flex justify-between text-[13px]">
                    <span className="font-semibold">
                      {type === "RESULT" ? t("analytics.result") : type === "EMERGENCY" ? t("analytics.emergency") : type === "SAME_DAY" ? t("analytics.sameDay") : type === "QUESTION" ? t("analytics.question") : t("analytics.error")}
                    </span>
                    <span className="text-muted-foreground">{count} ({pct.toFixed(1)}%)</span>
                  </div>
                  <div className="h-2 rounded bg-border overflow-hidden">
                    <div className={cn("h-full rounded min-w-[2px]", barColor[type] ?? "bg-muted-foreground")} style={{ width: `${Math.max(pct, 1)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {dailyRanked.length > 0 && (
        <div className="mt-5">
          <Card title={t("analytics.dailyTitle")}>
            <div className="flex flex-col gap-1.5">
              {dailyRanked.map(([day, cnt]) => (
                <div key={day} className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-sm">{day}</span>
                  <span className="font-bold text-sm">{cnt}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mt-5">
        <Card title={t("analytics.specialtyDistribution")}>
          {specRanked.map(([name, cnt], i) => (
            <div key={i} className="flex justify-between py-2 border-b border-border">
              <span className="text-sm">{name}</span>
              <span className="font-bold text-sm">{cnt}</span>
            </div>
          ))}
        </Card>
        <Card title={t("analytics.confidenceDistribution")}>
          {Object.entries(confCounts).map(([label, cnt], i) => (
            <div key={i} className="flex justify-between py-2 border-b border-border">
              <span className={cn("text-sm font-semibold", getConfidenceClass(label))}>{label}</span>
              <span className="font-bold text-sm">{cnt}</span>
            </div>
          ))}
        </Card>
      </div>

      <div className="mt-5">
        <Card title={t("analytics.confusionTitle")}>
          {confusionRows.length === 0 ? (
            <div className="text-muted-foreground text-[13px]">{t("analytics.confusionEmpty")}</div>
          ) : (
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b-2 border-border text-left">
                  <th className="p-2.5">{t("analytics.predicted")}</th>
                  <th className="p-2.5">{t("analytics.actualUser")}</th>
                  <th className="p-2.5">{t("analytics.count")}</th>
                </tr>
              </thead>
              <tbody>
                {confusionRows.map((row, i) => (
                  <tr key={i} className="border-b border-border">
                    <td className="p-2.5">{row.predicted}</td>
                    <td className="p-2.5 font-semibold">{row.actual}</td>
                    <td className="p-2.5 font-bold">{row.cnt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
