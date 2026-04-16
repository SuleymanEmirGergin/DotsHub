import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import fs from "fs";
import path from "path";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import type { DeploymentImpact, GuardrailsConfig, ImpactPeriod } from "@/lib/types/admin";

export const dynamic = "force-dynamic";

type Severity = "ok" | "info" | "warning" | "critical";

type Commentary = {
  severity: Severity;
  notes: string[];
  actions: string[];
};

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

function formatText(template: string, params: Record<string, string | number>): string {
  let out = template;
  for (const [key, value] of Object.entries(params)) {
    out = out.replaceAll(`{${key}}`, String(value));
  }
  return out;
}

function loadGuardrails() {
  try {
    const p = path.join(process.cwd(), "..", "config", "tuning_guardrails.json");
    return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch {
    return null;
  }
}

function buildImpactCommentary(
  impact: DeploymentImpact | null,
  guardrails: GuardrailsConfig | null,
  t: (key: string) => string,
): Commentary {
  const g = guardrails ?? { thresholds: {}, min_feedback_after: 30 };
  const thresholds = g.thresholds ?? {};

  const minN = Number(g.min_feedback_after ?? 30);
  const downMax = Number(thresholds.down_rate_max_delta ?? 0.15);
  const confMin = Number(thresholds.confidence_decrease_max ?? -0.10);
  const qMax = Number(thresholds.avg_questions_increase_max ?? 1.5);

  const afterTotal = impact?.after?.total ?? 0;

  const delta = impact?.delta ?? {};
  const dDown = delta.down_rate;
  const dConf = delta.avg_confidence;
  const dQ = delta.avg_questions;

  const notes: string[] = [];
  const actions: string[] = [];

  if (afterTotal < minN) {
    notes.push(
      formatText(t("deploymentImpact.noteInsufficientData"), {
        afterTotal,
        minN,
      }),
    );
    actions.push(t("deploymentImpact.actionWaitMoreFeedback"));
    return { severity: "info", notes, actions };
  }

  const bad: string[] = [];
  const good: string[] = [];

  if (typeof dDown === "number") {
    if (dDown > downMax) {
      bad.push(
        formatText(t("deploymentImpact.noteDownRateWorse"), {
          delta: dDown.toFixed(4),
          limit: downMax,
        }),
      );
    } else if (dDown < -0.01) {
      good.push(
        formatText(t("deploymentImpact.noteDownRateBetter"), {
          delta: dDown.toFixed(4),
        }),
      );
    } else {
      notes.push(
        formatText(t("deploymentImpact.noteDownRateStable"), {
          delta: dDown.toFixed(4),
        }),
      );
    }
  }

  if (typeof dConf === "number") {
    if (dConf < confMin) {
      bad.push(
        formatText(t("deploymentImpact.noteConfidenceDown"), {
          delta: dConf.toFixed(4),
          limit: confMin,
        }),
      );
    } else if (dConf > 0.02) {
      good.push(
        formatText(t("deploymentImpact.noteConfidenceUp"), {
          delta: dConf.toFixed(4),
        }),
      );
    } else {
      notes.push(
        formatText(t("deploymentImpact.noteConfidenceStable"), {
          delta: dConf.toFixed(4),
        }),
      );
    }
  }

  if (typeof dQ === "number") {
    if (dQ > qMax) {
      bad.push(
        formatText(t("deploymentImpact.noteQuestionsUp"), {
          delta: dQ.toFixed(3),
          limit: qMax,
        }),
      );
    } else if (dQ < -0.15) {
      good.push(
        formatText(t("deploymentImpact.noteQuestionsFaster"), {
          delta: dQ.toFixed(3),
        }),
      );
    } else {
      notes.push(
        formatText(t("deploymentImpact.noteQuestionsStable"), {
          delta: dQ.toFixed(3),
        }),
      );
    }
  }

  let severity: Severity = "ok";
  if (bad.length >= 2) severity = "critical";
  else if (bad.length === 1) severity = "warning";

  if (good.length) notes.unshift(...good);
  if (bad.length) notes.unshift(...bad);

  if (severity === "critical") {
    actions.unshift(t("deploymentImpact.actionCritical"));
  } else if (severity === "warning") {
    actions.unshift(t("deploymentImpact.actionWarning"));
  } else {
    actions.unshift(t("deploymentImpact.actionOk"));
  }

  actions.push(t("deploymentImpact.actionSynonym"));
  actions.push(t("deploymentImpact.actionQuestion"));

  return { severity, notes, actions };
}

function SevPill({ s, t }: { s: string; t: (key: string) => string }) {
  const m: Record<string, { class: string; label: string }> = {
    ok: { class: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300", label: t("deploymentImpact.severityOk") },
    info: { class: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300", label: t("deploymentImpact.severityInfo") },
    warning: { class: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300", label: t("deploymentImpact.severityWarning") },
    critical: { class: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300", label: t("deploymentImpact.severityCritical") },
  };
  const x = m[s] ?? m.info;
  return (
    <span className={cn("py-1 px-2.5 rounded-full font-black text-xs", x.class)}>
      {x.label}
    </span>
  );
}

function Sparkline({ data, label }: { data: number[]; label: string }) {
  if (!data || data.length === 0) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = 100 - ((v - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="mt-2">
      <div className="text-[11px] text-muted-foreground mb-1">{label}</div>
      <svg
        width="100%"
        height="40"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="border border-border rounded bg-accent"
      >
        <polyline
          points={points}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

export default async function DeploymentImpactPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);
  const { id } = await params;

  let impact: DeploymentImpact | null = null;
  try {
    const reportsDir = path.join(process.cwd(), "..", "backend", "reports");
    const files = fs
      .readdirSync(reportsDir)
      .filter((f) => f.startsWith("impact_") && f.includes(id) && f.endsWith(".json"))
      .sort();

    if (files.length > 0) {
      const latest = files[files.length - 1];
      const p = path.join(reportsDir, latest);
      impact = JSON.parse(fs.readFileSync(p, "utf-8"));
    }
  } catch (e) {
    console.error("Failed to load impact:", e);
  }

  if (!impact) {
    return (
      <div className="p-6">
        <div className="max-w-[900px] mx-auto">
          <h1 className="text-[26px] font-black">{t("deploymentImpact.title")}</h1>
          <div className="mt-3.5 p-5 bg-red-100 dark:bg-red-900/30 rounded-xl text-red-800 dark:text-red-300">
            {formatText(t("deploymentImpact.noReport"), { id })}
          </div>
          <div className="mt-3.5">
            <a href="/admin/deployments" className="font-extrabold text-primary">
              {t("deploymentImpact.backToDeployments")}
            </a>
          </div>
        </div>
      </div>
    );
  }

  const guardrails = loadGuardrails();
  const commentary = buildImpactCommentary(impact, guardrails, t);

  const before: ImpactPeriod = impact.before ?? {};
  const after: ImpactPeriod = impact.after ?? {};
  const delta: DeploymentImpact["delta"] = impact.delta ?? {};

  const dailySeries = after.daily_series || [];
  const downRateSeries = dailySeries.map((d: { down_rate?: number; confidence?: number }) => d.down_rate ?? 0);
  const confSeries = dailySeries.map((d: { down_rate?: number; confidence?: number }) => d.confidence ?? 0);

  return (
    <div className="p-6 font-sans bg-background text-foreground min-h-screen">
      <div className="max-w-[1000px] mx-auto">
        <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.deployments"), href: "/admin/deployments" }, { label: t("deploymentImpact.breadcrumb") }]} />
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-[26px] font-black m-0">{t("deploymentImpact.title")}</h1>
            <div className="text-muted-foreground mt-1 text-[13px]">
              {t("deploymentImpact.deploymentLabel")}: {id}
            </div>
          </div>
          <a href="/admin/deployments" className="font-extrabold text-primary no-underline">
            {t("deploymentImpact.backToDeployments")}
          </a>
        </div>

        <div className="mt-3.5 border border-border rounded-2xl p-4 bg-card">
          <div className="flex justify-between items-center">
            <div className="font-black text-base">{t("deploymentImpact.commentaryTitle")}</div>
            <SevPill s={commentary.severity} t={t} />
          </div>
          <div className="mt-2.5 text-primary">
            <div className="text-xs text-muted-foreground">{t("deploymentImpact.findings")}</div>
            <ul className="mt-2 pl-[18px]">
              {commentary.notes.map((x, i) => (
                <li key={i} className="mb-1.5">{x}</li>
              ))}
            </ul>
            <div className="text-xs text-muted-foreground mt-2.5">{t("deploymentImpact.recommendedActions")}</div>
            <ol className="mt-2 pl-[18px]">
              {commentary.actions.map((x, i) => (
                <li key={i} className="mb-1.5">{x}</li>
              ))}
            </ol>
          </div>
        </div>

        <div className="mt-3.5 grid grid-cols-3 gap-3.5">
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{t("deploymentImpact.sampleSize")}</div>
            <div className="mt-2 text-2xl font-black">
              {before.total ?? 0} → {after.total ?? 0}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              d {((after.total ?? 0) - (before.total ?? 0)) >= 0 ? "+" : ""}{((after.total ?? 0) - (before.total ?? 0))}
            </div>
          </div>
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{t("deploymentImpact.downRate")}</div>
            <div className="mt-2 text-2xl font-black">
              {((before.down_rate ?? 0) * 100).toFixed(1)}% → {((after.down_rate ?? 0) * 100).toFixed(1)}%
            </div>
            <div className={cn("mt-1 text-xs", (delta.down_rate ?? 0) > 0 ? "text-red-800 dark:text-red-400" : "text-teal-800 dark:text-teal-400")}>
              d {(delta.down_rate ?? 0) >= 0 ? "+" : ""}{((delta.down_rate ?? 0) * 100).toFixed(2)}%
            </div>
            <Sparkline data={downRateSeries} label={t("deploymentImpact.last7Days")} />
          </div>
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{t("deploymentImpact.avgConfidence")}</div>
            <div className="mt-2 text-2xl font-black">
              {(before.avg_confidence ?? 0).toFixed(3)} → {(after.avg_confidence ?? 0).toFixed(3)}
            </div>
            <div className={cn("mt-1 text-xs", (delta.avg_confidence ?? 0) >= 0 ? "text-teal-800 dark:text-teal-400" : "text-red-800 dark:text-red-400")}>
              d {(delta.avg_confidence ?? 0) >= 0 ? "+" : ""}{(delta.avg_confidence ?? 0).toFixed(4)}
            </div>
            <Sparkline data={confSeries} label={t("deploymentImpact.last7Days")} />
          </div>
          <div className="border border-border rounded-xl p-4 bg-card">
            <div className="text-xs text-muted-foreground font-bold">{t("deploymentImpact.avgQuestions")}</div>
            <div className="mt-2 text-2xl font-black">
              {(before.avg_questions ?? 0).toFixed(1)} → {(after.avg_questions ?? 0).toFixed(1)}
            </div>
            <div className={cn("mt-1 text-xs", (delta.avg_questions ?? 0) <= 0 ? "text-teal-800 dark:text-teal-400" : "text-red-800 dark:text-red-400")}>
              d {(delta.avg_questions ?? 0) >= 0 ? "+" : ""}{(delta.avg_questions ?? 0).toFixed(2)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
