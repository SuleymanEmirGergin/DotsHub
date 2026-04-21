"use client";

/**
 * Phase B7 — Daily summary panel for /admin/analytics.
 *
 * Pulls aggregated metrics from the Next.js proxy
 * `/api/admin/daily-summary` (→ backend `/admin/stats/daily-summary`)
 * and renders three visualisations:
 *
 *   1. Daily throughput (bar chart, last N days)
 *   2. Urgency distribution (horizontal bar, colour-coded per severity)
 *   3. Top specialties (horizontal bar, top 5)
 *
 * Plus two scalar stat cards at the top: total sessions in window +
 * low-confidence rate. Confidence trend is rendered as a mini line
 * chart tucked inside the total card.
 *
 * Why a client component
 * ----------------------
 * Recharts bundles its own client-side ResponsiveContainer + Tooltip
 * that require the DOM. A server-side fetch into a client renderer
 * would split concerns but we'd need two files; for a panel this
 * small the tax isn't worth it. Data refetches every 30s via setInterval;
 * no SWR/React Query dependency to keep bundle tight.
 *
 * Recharts v3 + React 19 + Next 15 are tested compatible as of the
 * time this file was added (recharts 3.8.1 is the version pinned in
 * package.json). If a future upgrade breaks, see recharts/issues for
 * React 19 compatibility updates.
 */

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type DailySummary = {
  window_days: number;
  total: number;
  daily_totals: Array<{ day: string; count: number }>;
  by_urgency: Record<string, number>;
  by_envelope?: Record<string, number>;
  funnel?: {
    started: number;
    questioned: number;
    resulted: number;
    feedback: number;
  };
  top_specialties: Array<{ name: string; count: number }>;
  avg_confidence_by_day: Array<{ day: string; avg: number | null }>;
  low_confidence_count: number;
  low_confidence_pct: number;
};

type WindowDays = 7 | 14 | 30;

// Urgency severity colour mapping. Aligned with the mobile
// result-screen palette so the user-facing green/amber/red matches
// what operators see here.
const URGENCY_COLORS: Record<string, string> = {
  ROUTINE: "#10b981", // green
  WITHIN_3_DAYS: "#fbbf24", // amber
  SAME_DAY: "#f97316", // orange
  ER_NOW: "#ef4444", // red
  UNKNOWN: "#6b7280", // gray
};

const URGENCY_LABEL_TR: Record<string, string> = {
  ROUTINE: "Rutin",
  WITHIN_3_DAYS: "3 gün içinde",
  SAME_DAY: "Aynı gün",
  ER_NOW: "Acil",
  UNKNOWN: "Bilinmeyen",
};

function formatDayTR(isoDay: string): string {
  // Keep rendering server-locale-neutral; just "MM/DD" is enough for
  // a 7-day view. Longer windows might want a different format.
  const [, m, d] = isoDay.split("-");
  return `${d}/${m}`;
}

export default function DailySummaryPanel() {
  const [data, setData] = useState<DailySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Window selector — 7 default to keep the first render tight (fewer
  // bars in the daily-throughput chart). 14/30 surface weekly/monthly
  // trend without requiring a separate endpoint; backend clamps at 30.
  const [windowDays, setWindowDays] = useState<WindowDays>(7);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const r = await fetch(`/api/admin/daily-summary?days=${windowDays}`, {
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = (await r.json()) as DailySummary;
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "fetch failed");
      }
    }

    load();
    const id = setInterval(load, 30_000); // 30s auto-refresh
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [windowDays]);

  const windowSelector = (
    <div className="flex gap-1 mb-4" role="group" aria-label="Zaman aralığı">
      {([7, 14, 30] as const).map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => setWindowDays(n)}
          className={
            "px-3 py-1 text-xs rounded-md border transition-colors " +
            (windowDays === n
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card text-muted-foreground hover:bg-muted")
          }
          aria-pressed={windowDays === n}
        >
          {n === 7 ? "7 gün" : n === 14 ? "14 gün" : "30 gün"}
        </button>
      ))}
    </div>
  );

  if (error) {
    return (
      <div>
        {windowSelector}
        <div className="p-4 rounded-xl border border-border bg-card text-sm text-red-500">
          Analitik yüklenemedi: {error}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        {windowSelector}
        <div className="p-4 rounded-xl border border-border bg-card text-sm text-muted-foreground animate-pulse">
          Son {windowDays} gün yükleniyor…
        </div>
      </div>
    );
  }

  // Urgency → ordered array for chart. Severity order (routine → er)
  // reads left-to-right as risk intensifies; colour-coded too so the
  // glance carries the signal without reading labels.
  const urgencyOrder = ["ROUTINE", "WITHIN_3_DAYS", "SAME_DAY", "ER_NOW", "UNKNOWN"];
  const urgencyData = urgencyOrder
    .map((key) => ({
      key,
      label: URGENCY_LABEL_TR[key] ?? key,
      count: data.by_urgency[key] ?? 0,
      color: URGENCY_COLORS[key],
    }))
    .filter((r) => r.count > 0);

  const dailyChartData = data.daily_totals.map((d) => ({
    day: formatDayTR(d.day),
    count: d.count,
  }));

  const confTrend = data.avg_confidence_by_day
    .map((d) => ({ day: formatDayTR(d.day), avg: d.avg }))
    .filter((d) => d.avg !== null) as Array<{ day: string; avg: number }>;

  // ─── Funnel stages ──────────────────────────────────────────────
  // Each step's conversion rate is relative to the *previous* step.
  // The first step anchors at 100% as the baseline. "No data" degrades
  // to hiding the card so we don't render an empty funnel.
  const funnel = data.funnel;
  const funnelStages = funnel
    ? [
        { key: "started", label: "Semptom girildi", count: funnel.started },
        { key: "questioned", label: "Soru-cevap", count: funnel.questioned },
        { key: "resulted", label: "Sonuç alındı", count: funnel.resulted },
        { key: "feedback", label: "Geri bildirim", count: funnel.feedback },
      ]
    : [];
  const maxFunnel = funnelStages.reduce((m, s) => Math.max(m, s.count), 0);

  return (
    <div>
      {windowSelector}
    <div className="grid gap-4 grid-cols-1 md:grid-cols-3 mb-6">
      {/* ───── Card 1: Total + confidence trend ───── */}
      <div className="p-4 rounded-xl border border-border bg-card text-card-foreground md:col-span-1">
        <div className="text-xs text-muted-foreground">
          Son {data.window_days} gün · toplam
        </div>
        <div className="text-[32px] font-extrabold mt-1">{data.total}</div>
        <div className="text-xs text-muted-foreground mb-2">
          Düşük güven: {(data.low_confidence_pct * 100).toFixed(1)}% (
          {data.low_confidence_count})
        </div>
        {confTrend.length >= 2 && (
          <div style={{ height: 60 }}>
            <ResponsiveContainer>
              <LineChart data={confTrend}>
                <YAxis hide domain={[0, 1]} />
                <Line
                  type="monotone"
                  dataKey="avg"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--dash-bg-card, #0b0b0b)",
                    border: "1px solid var(--dash-border, #333)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  // Recharts' Formatter type allows value to be
                  // undefined in edge cases; guard + stringify so
                  // types line up without an `any` cast.
                  formatter={(v) =>
                    typeof v === "number"
                      ? [v.toFixed(2), "Ort. güven"]
                      : ["—", "Ort. güven"]
                  }
                  labelFormatter={(l) => `Gün: ${l}`}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ───── Card 2: Daily throughput ───── */}
      <div className="p-4 rounded-xl border border-border bg-card text-card-foreground md:col-span-2">
        <div className="text-xs text-muted-foreground mb-2">Günlük triyaj sayısı</div>
        <div style={{ height: 180 }}>
          <ResponsiveContainer>
            <BarChart data={dailyChartData}>
              <CartesianGrid stroke="var(--dash-border, #333)" strokeDasharray="3 3" />
              <XAxis
                dataKey="day"
                stroke="var(--dash-text-muted, #999)"
                tick={{ fontSize: 11 }}
              />
              <YAxis
                stroke="var(--dash-text-muted, #999)"
                tick={{ fontSize: 11 }}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--dash-bg-card, #0b0b0b)",
                  border: "1px solid var(--dash-border, #333)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                cursor={{ fill: "rgba(99, 102, 241, 0.08)" }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ───── Card 3: Urgency distribution ───── */}
      <div className="p-4 rounded-xl border border-border bg-card text-card-foreground">
        <div className="text-xs text-muted-foreground mb-2">Aciliyet dağılımı</div>
        {urgencyData.length === 0 ? (
          <div className="text-xs text-muted-foreground py-6 text-center">
            Henüz veri yok
          </div>
        ) : (
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <BarChart data={urgencyData} layout="vertical">
                <CartesianGrid stroke="var(--dash-border, #333)" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  stroke="var(--dash-text-muted, #999)"
                  tick={{ fontSize: 11 }}
                  allowDecimals={false}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  stroke="var(--dash-text-muted, #999)"
                  tick={{ fontSize: 11 }}
                  width={90}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--dash-bg-card, #0b0b0b)",
                    border: "1px solid var(--dash-border, #333)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  cursor={{ fill: "rgba(99, 102, 241, 0.08)" }}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {urgencyData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ───── Card 4: Top specialties ───── */}
      <div className="p-4 rounded-xl border border-border bg-card text-card-foreground md:col-span-2">
        <div className="text-xs text-muted-foreground mb-2">
          En çok önerilen branşlar (Top 5, RESULT envelope)
        </div>
        {data.top_specialties.length === 0 ? (
          <div className="text-xs text-muted-foreground py-6 text-center">
            Henüz RESULT yok
          </div>
        ) : (
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <BarChart data={data.top_specialties} layout="vertical">
                <CartesianGrid stroke="var(--dash-border, #333)" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  stroke="var(--dash-text-muted, #999)"
                  tick={{ fontSize: 11 }}
                  allowDecimals={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke="var(--dash-text-muted, #999)"
                  tick={{ fontSize: 11 }}
                  width={130}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--dash-bg-card, #0b0b0b)",
                    border: "1px solid var(--dash-border, #333)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  cursor={{ fill: "rgba(99, 102, 241, 0.08)" }}
                />
                <Bar dataKey="count" fill="#10b981" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>

    {/* ───── Funnel card (full-width) ─────
        Shows the drop-off between: symptom → Q&A → result → feedback.
        Horizontal bar widths are relative to the first stage (max), so
        the "funnel" shape reads left-to-right as diminishing width.
        Conversion % labels use stage-over-previous-stage ratio, which
        is the operational metric — how many users kept going at each
        step. Zero-total windows hide the card entirely. */}
    {funnelStages.length > 0 && maxFunnel > 0 && (
      <div className="p-4 rounded-xl border border-border bg-card text-card-foreground mb-6">
        <div className="text-xs text-muted-foreground mb-3">
          Dönüşüm hunisi · son {data.window_days} gün
        </div>
        <div className="flex flex-col gap-3">
          {funnelStages.map((stage, i) => {
            const widthPct = (stage.count / maxFunnel) * 100;
            const prev = i > 0 ? funnelStages[i - 1].count : null;
            const conv =
              prev !== null && prev > 0
                ? (stage.count / prev) * 100
                : null;
            return (
              <div key={stage.key} className="flex flex-col gap-1">
                <div className="flex justify-between text-[13px]">
                  <span className="font-semibold">{stage.label}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {stage.count.toLocaleString("tr-TR")}
                    {conv !== null && (
                      <span className="ml-2 text-xs">
                        ({conv.toFixed(1)}%)
                      </span>
                    )}
                  </span>
                </div>
                <div className="h-2.5 rounded bg-border overflow-hidden">
                  <div
                    className="h-full rounded bg-indigo-500 dark:bg-indigo-400 min-w-[2px] transition-all"
                    style={{ width: `${Math.max(widthPct, 1)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    )}
    </div>
  );
}
