import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import DailySummaryPanel from "./DailySummaryPanel";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

function Stat({
  label,
  value,
  sub,
  spark,
}: {
  label: string;
  value: string | number;
  sub?: string;
  spark?: number[];
}) {
  return (
    <div className="p-4 rounded-xl border border-border bg-card text-card-foreground">
      <div className="flex justify-between items-start gap-2">
        <div className="text-xs text-muted-foreground">{label}</div>
        {spark && spark.length > 1 && <Sparkline values={spark} />}
      </div>
      <div className="text-[28px] font-extrabold mt-1">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

// Tiny inline SVG sparkline — C3 trend visualization for the B2
// accuracy cards. Renders 7 days of daily values as a normalized
// polyline + dotted endpoint. No external dep.
function Sparkline({
  values,
  width = 80,
  height = 22,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  const safe = values.filter((v) => Number.isFinite(v));
  if (safe.length < 2) return null;
  const min = Math.min(...safe);
  const max = Math.max(...safe);
  const range = max - min || 1;
  const step = width / (safe.length - 1);
  const pts = safe
    .map((v, i) => {
      const x = i * step;
      // Flip Y: higher value → lower y (svg coord).
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const [lastX, lastY] = pts.split(" ").slice(-1)[0].split(",");
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
      <polyline
        points={pts}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className="text-muted-foreground"
      />
      <circle cx={lastX} cy={lastY} r={2} className="fill-foreground" />
    </svg>
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
  ((specDist ?? []) as Array<{ recommended_specialty_tr?: string | null }>).forEach((s) => {
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
  ((confDist ?? []) as Array<{ confidence_label_tr?: string | null }>).forEach((s) => {
    const label = s.confidence_label_tr || unknown;
    confCounts[label] = (confCounts[label] || 0) + 1;
  });

  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const sevenDaysAgoIso = sevenDaysAgo.toISOString();
  const { data: dailySessions } = await sb
    .from("triage_sessions")
    .select("created_at")
    .gte("created_at", sevenDaysAgoIso);

  // ── 7-day accuracy KPIs (B2) ─────────────────────────────────────────
  // 1) Top-1 specialty accuracy (proxy): 1 - (down feedback with
  //    user_selected_specialty_id / RESULT sessions in last 7d).
  // 2) Low-confidence rate: RESULT sessions with confidence_0_1 < 0.35.
  // 3) Feedback override rate: feedback entries with user_selected_
  //    specialty_id / total feedback in last 7d.
  const LOW_CONF_THRESHOLD = 0.35;

  const { count: result7dTotal } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "RESULT")
    .gte("created_at", sevenDaysAgoIso);

  const { count: result7dLowConf } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "RESULT")
    .gte("created_at", sevenDaysAgoIso)
    .lt("confidence_0_1", LOW_CONF_THRESHOLD);

  const { count: feedback7dTotal } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .gte("created_at", sevenDaysAgoIso);

  const { count: feedback7dOverrides } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .gte("created_at", sevenDaysAgoIso)
    .not("user_selected_specialty_id", "is", null);

  const { count: feedback7dDown } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .gte("created_at", sevenDaysAgoIso)
    .eq("rating", "down")
    .not("user_selected_specialty_id", "is", null);

  const top1AccuracyPct = (result7dTotal ?? 0) > 0
    ? Math.max(0, 100 - (100 * (feedback7dDown ?? 0)) / (result7dTotal ?? 1))
    : null;
  const lowConfPct = (result7dTotal ?? 0) > 0
    ? (100 * (result7dLowConf ?? 0)) / (result7dTotal ?? 1)
    : null;
  const overridePct = (feedback7dTotal ?? 0) > 0
    ? (100 * (feedback7dOverrides ?? 0)) / (feedback7dTotal ?? 1)
    : null;

  // ── 7-day daily buckets for sparkline trends (C3) ───────────────────
  // Fetch raw rows once, bucket client-side. Cheaper than 7 separate
  // counts per metric (would be 7*3=21 count queries).
  const { data: resultRows7d } = await sb
    .from("triage_sessions")
    .select("created_at,confidence_0_1")
    .eq("envelope_type", "RESULT")
    .gte("created_at", sevenDaysAgoIso);
  const { data: feedbackRows7d } = await sb
    .from("triage_feedback")
    .select("created_at,rating,user_selected_specialty_id")
    .gte("created_at", sevenDaysAgoIso);

  function dayKey(iso: string): string {
    return new Date(iso).toISOString().slice(0, 10);
  }
  // Build an ordered list of the last 7 day keys (today + prior 6),
  // oldest first so the sparkline reads left-to-right chronologically.
  const dayKeys: string[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - i);
    dayKeys.push(d.toISOString().slice(0, 10));
  }

  const dailyResult: Record<string, { total: number; lowConf: number }> = {};
  for (const k of dayKeys) dailyResult[k] = { total: 0, lowConf: 0 };
  for (const row of (resultRows7d ?? []) as Array<{ created_at: string; confidence_0_1?: number | null }>) {
    const k = dayKey(row.created_at);
    if (dailyResult[k] === undefined) continue;
    dailyResult[k].total += 1;
    const conf = typeof row.confidence_0_1 === "number" ? row.confidence_0_1 : null;
    if (conf !== null && conf < LOW_CONF_THRESHOLD) {
      dailyResult[k].lowConf += 1;
    }
  }

  const dailyFeedback: Record<string, { total: number; overrides: number; downWithOverride: number }> = {};
  for (const k of dayKeys) dailyFeedback[k] = { total: 0, overrides: 0, downWithOverride: 0 };
  for (const row of (feedbackRows7d ?? []) as Array<{
    created_at: string;
    user_selected_specialty_id?: string | null;
    rating?: string | null;
  }>) {
    const k = dayKey(row.created_at);
    if (dailyFeedback[k] === undefined) continue;
    dailyFeedback[k].total += 1;
    const overridden = !!row.user_selected_specialty_id;
    if (overridden) {
      dailyFeedback[k].overrides += 1;
      if (row.rating === "down") dailyFeedback[k].downWithOverride += 1;
    }
  }

  // Derive per-day percentages for each of the three B2 cards.
  const top1AccuracySpark: number[] = dayKeys.map((k) => {
    const total = dailyResult[k].total;
    if (total === 0) return 100; // "no data" days anchor at 100 for visual baseline
    return Math.max(0, 100 - (100 * dailyFeedback[k].downWithOverride) / total);
  });
  const lowConfSpark: number[] = dayKeys.map((k) => {
    const total = dailyResult[k].total;
    if (total === 0) return 0;
    return (100 * dailyResult[k].lowConf) / total;
  });
  const overrideSpark: number[] = dayKeys.map((k) => {
    const total = dailyFeedback[k].total;
    if (total === 0) return 0;
    return (100 * dailyFeedback[k].overrides) / total;
  });

  // ── 7-day LLM health KPIs (A1 telemetri) ────────────────────────────
  // Source: llm_calls table (populated by services/llm_nlu.py _log_llm_call).
  // Alert signal: success_rate < 80% warrants investigation (usually an
  // auth regression or upstream provider outage).
  const { data: llmCallsRows } = await sb
    .from("llm_calls")
    .select("success,latency_ms,error_type")
    .gte("created_at", sevenDaysAgoIso);

  const llmCallsArr = (llmCallsRows ?? []) as {
    success: boolean | null;
    latency_ms: number | null;
    error_type: string | null;
  }[];
  const llmCallTotal = llmCallsArr.length;
  const llmSuccessCount = llmCallsArr.filter((r) => r.success === true).length;
  const llmSuccessPct = llmCallTotal > 0
    ? (100 * llmSuccessCount) / llmCallTotal
    : null;
  const llmAvgLatencyMs = llmCallTotal > 0
    ? Math.round(
        llmCallsArr.reduce((acc, r) => acc + (r.latency_ms ?? 0), 0) /
          llmCallTotal
      )
    : null;
  const llmErrorTypeCounts: Record<string, number> = {};
  for (const r of llmCallsArr) {
    if (r.success === true) continue;
    const et = r.error_type || "unknown";
    llmErrorTypeCounts[et] = (llmErrorTypeCounts[et] || 0) + 1;
  }
  const llmErrorTypeRanked = Object.entries(llmErrorTypeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const LLM_SUCCESS_ALERT_THRESHOLD = 80;
  const llmHealthStatus: "ok" | "warn" | "no-data" =
    llmSuccessPct === null
      ? "no-data"
      : llmSuccessPct >= LLM_SUCCESS_ALERT_THRESHOLD
        ? "ok"
        : "warn";

  const dailyCounts: Record<string, number> = {};
  ((dailySessions ?? []) as Array<{ created_at: string }>).forEach((s) => {
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

  const confusionSessionIds = ((confusionRaw ?? []) as Array<{ session_id: string }>).map((f) => f.session_id);
  let confusionRows: { predicted: string; actual: string; cnt: number }[] = [];

  if (confusionSessionIds.length > 0) {
    const { data: confSessions } = await sb
      .from("triage_sessions")
      .select("id,recommended_specialty_tr")
      .in("id", confusionSessionIds.slice(0, 100));

    const sessionSpec: Record<string, string> = {};
    ((confSessions ?? []) as Array<{ id: string; recommended_specialty_tr?: string | null }>).forEach((s) => {
      sessionSpec[s.id] = s.recommended_specialty_tr ?? unknown;
    });

    const confPairs: Record<string, number> = {};
    ((confusionRaw ?? []) as Array<{ session_id: string; user_selected_specialty_id?: string | null }>).forEach((f) => {
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
        <div className="flex flex-wrap gap-2">
          <Button variant="link" size="sm" className="text-emerald-600 p-0 h-auto" asChild>
            <Link href="/admin/live">{t("analytics.liveLink")} &rarr;</Link>
          </Button>
          <Button variant="link" size="sm" className="p-0 h-auto" asChild>
            <Link href="/admin/feedback">{t("analytics.feedbackLink")} &rarr;</Link>
          </Button>
          <Button variant="link" size="sm" className="p-0 h-auto" asChild>
            <Link href="/admin/sessions">{t("analytics.sessionsLink")} &rarr;</Link>
          </Button>
          <Button variant="link" size="sm" className="p-0 h-auto" asChild>
            <Link href="/admin/tuning-report">{t("analytics.tuningLink")} &rarr;</Link>
          </Button>
        </div>
      </div>

      {/* Phase B7 — Daily summary recharts panel. Client-side fetches
          /api/admin/daily-summary every 30s. Rendered above the static
          stat cards so the visual takeaway (bugünkü trend) comes
          first when the page opens. */}
      <div className="mt-5">
        <DailySummaryPanel />
      </div>

      <div className="grid grid-cols-4 gap-3 mt-5">
        <Stat label={t("analytics.totalSessions")} value={totalSessions ?? 0} />
        <Stat label={t("analytics.result")} value={resultSessions ?? 0} />
        <Stat label={t("analytics.emergency")} value={emergencySessions ?? 0} />
        <Stat label={t("analytics.feedback")} value={`${fbUpCount ?? 0} / ${fbDownCount ?? 0}`} sub={t("analytics.feedbackSub")} />
      </div>

      <div className="mt-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("analytics.accuracy7dTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              <Stat
                label={t("analytics.top1Accuracy")}
                value={top1AccuracyPct === null ? "—" : `${top1AccuracyPct.toFixed(1)}%`}
                sub={top1AccuracyPct === null ? t("analytics.accuracyNoData") : t("analytics.top1AccuracySub")}
                spark={top1AccuracySpark}
              />
              <Stat
                label={t("analytics.lowConfRate")}
                value={lowConfPct === null ? "—" : `${lowConfPct.toFixed(1)}%`}
                sub={lowConfPct === null ? t("analytics.accuracyNoData") : t("analytics.lowConfRateSub")}
                spark={lowConfSpark}
              />
              <Stat
                label={t("analytics.feedbackOverrideRate")}
                value={overridePct === null ? "—" : `${overridePct.toFixed(1)}%`}
                sub={overridePct === null ? t("analytics.accuracyNoData") : t("analytics.feedbackOverrideRateSub")}
                spark={overrideSpark}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mt-5">
        <Card>
          <CardHeader>
            <CardTitle
              className={cn(
                "text-base flex items-center gap-2",
                llmHealthStatus === "warn" && "text-red-700 dark:text-red-400",
              )}
            >
              {t("analytics.llmHealthTitle")}
              {llmHealthStatus === "warn" && (
                <span className="text-xs bg-red-100 dark:bg-red-950 text-red-800 dark:text-red-200 px-2 py-0.5 rounded">
                  {t("analytics.llmHealthAlert")}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              <Stat
                label={t("analytics.llmCalls")}
                value={llmCallTotal}
                sub={t("analytics.llmCallsSub")}
              />
              <Stat
                label={t("analytics.llmSuccessRate")}
                value={llmSuccessPct === null ? "—" : `${llmSuccessPct.toFixed(1)}%`}
                sub={
                  llmSuccessPct === null
                    ? t("analytics.accuracyNoData")
                    : llmHealthStatus === "warn"
                      ? `${t("analytics.llmSuccessRateSub")} (<${LLM_SUCCESS_ALERT_THRESHOLD}%)`
                      : t("analytics.llmSuccessRateSub")
                }
              />
              <Stat
                label={t("analytics.llmAvgLatency")}
                value={llmAvgLatencyMs === null ? "—" : `${llmAvgLatencyMs} ms`}
                sub={t("analytics.llmAvgLatencySub")}
              />
            </div>
            {llmErrorTypeRanked.length > 0 && (
              <div className="mt-4">
                <div className="text-xs text-muted-foreground mb-2">
                  {t("analytics.llmErrorTypes")}
                </div>
                <div className="flex flex-wrap gap-2">
                  {llmErrorTypeRanked.map(([et, cnt]) => (
                    <div
                      key={et}
                      className="text-xs px-2 py-1 rounded border border-border bg-muted"
                    >
                      <span className="font-mono">{et}</span>{" "}
                      <span className="font-bold">{cnt}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {envelopeDistribution.length > 0 && (
        <div className="mt-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("analytics.resultTypeDistribution")}</CardTitle>
            </CardHeader>
            <CardContent>
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
            </CardContent>
          </Card>
        </div>
      )}

      {dailyRanked.length > 0 && (
        <div className="mt-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("analytics.dailyTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
            <div className="flex flex-col gap-1.5">
              {dailyRanked.map(([day, cnt]) => (
                <div key={day} className="flex justify-between py-1.5 border-b border-border">
                  <span className="text-sm">{day}</span>
                  <span className="font-bold text-sm">{cnt}</span>
                </div>
              ))}
            </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mt-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("analytics.specialtyDistribution")}</CardTitle>
          </CardHeader>
          <CardContent>
          {specRanked.map(([name, cnt], i) => (
            <div key={i} className="flex justify-between py-2 border-b border-border">
              <span className="text-sm">{name}</span>
              <span className="font-bold text-sm">{cnt}</span>
            </div>
          ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("analytics.confidenceDistribution")}</CardTitle>
          </CardHeader>
          <CardContent>
          {Object.entries(confCounts).map(([label, cnt], i) => (
            <div key={i} className="flex justify-between py-2 border-b border-border">
              <span className={cn("text-sm font-semibold", getConfidenceClass(label))}>{label}</span>
              <span className="font-bold text-sm">{cnt}</span>
            </div>
          ))}
          </CardContent>
        </Card>
      </div>

      <div className="mt-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("analytics.confusionTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
