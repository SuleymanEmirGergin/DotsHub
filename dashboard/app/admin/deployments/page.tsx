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

type Health = {
  overall: "INFO" | "OK" | "WARN" | "CRIT";
  samples: number;
  low_conf_rate: number;
  high_risk_rate: number;
};

// Shape of a guardrails.json file on disk. Kept permissive
// (everything optional) because the file ships with sane defaults and
// ops may add new thresholds without bumping this TS type.
type Guardrails = {
  thresholds?: {
    down_rate_max_delta?: number;
    confidence_decrease_max?: number;
    avg_questions_increase_max?: number;
  };
  min_feedback_after?: number;
};

// Minimal shape of a deployment row as it appears in Supabase (+ the
// in-memory annotations this page layers on top). Not exhaustive —
// JSX accesses additional fields (git_sha, author, etc.) via the
// index signature rather than forcing us to enumerate every column.
type DeploymentRow = {
  id: string;
  created_at: string;
  status?: string | null;
  title?: string | null;
  [key: string]: unknown;
};

type DeploymentWithImpact = DeploymentRow & {
  _impact: ImpactReport | null;
  _sev: "info" | "ok" | "warning" | "critical" | null;
};

// Permissive shape for the impact report JSON. Every numeric stat
// is allowed via index signature so the report generator can add
// fields without touching this file. `after.total` / `delta.down_rate`
// accesses below work because we declare those slots as `number`.
type ImpactStats = {
  [key: string]: number | undefined;
};

type ImpactReport = {
  before?: ImpactStats;
  after?: ImpactStats;
  delta?: ImpactStats;
  [key: string]: unknown;
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

function loadGuardrails(): Guardrails | null {
  try {
    const p = path.join(process.cwd(), "..", "config", "tuning_guardrails.json");
    return JSON.parse(fs.readFileSync(p, "utf-8")) as Guardrails;
  } catch {
    return null;
  }
}

function findLatestImpactForDeployment(deploymentId: string): ImpactReport | null {
  try {
    const reportsDir = path.join(process.cwd(), "..", "backend", "reports");
    if (!fs.existsSync(reportsDir)) return null;

    const files = fs
      .readdirSync(reportsDir)
      .filter((f) => f.startsWith("impact_") && f.includes(deploymentId) && f.endsWith(".json"))
      .sort();
    if (files.length === 0) return null;

    const latest = files[files.length - 1];
    const p = path.join(reportsDir, latest);
    return JSON.parse(fs.readFileSync(p, "utf-8")) as ImpactReport;
  } catch {
    return null;
  }
}

function computeSeverity(
  impact: ImpactReport,
  guardrails: Guardrails | null,
): "info" | "ok" | "warning" | "critical" {
  const g = guardrails ?? { thresholds: {}, min_feedback_after: 30 };
  const t = g.thresholds ?? {};

  const minN = Number(g.min_feedback_after ?? 30);
  const downMax = Number(t.down_rate_max_delta ?? 0.15);
  const confMin = Number(t.confidence_decrease_max ?? -0.1);
  const qMax = Number(t.avg_questions_increase_max ?? 1.5);

  const afterFb = impact?.after?.total ?? 0;
  if (afterFb < minN) return "info";

  const d = impact?.delta ?? {};
  let bad = 0;

  if (typeof d.down_rate === "number" && d.down_rate > downMax) bad++;
  if (typeof d.avg_confidence === "number" && d.avg_confidence < confMin) bad++;
  if (typeof d.avg_questions === "number" && d.avg_questions > qMax) bad++;

  if (bad >= 2) return "critical";
  if (bad === 1) return "warning";
  return "ok";
}

function getStatusLabel(status: string, t: (key: string) => string): string {
  if (status === "applied") return t("deploymentsPage.statusApplied");
  if (status === "rolled_back_pending") return t("deploymentsPage.statusRolledBackPending");
  if (status === "rolled_back") return t("deploymentsPage.statusRolledBack");
  return status;
}

function getSeverityLabel(severity: string, t: (key: string) => string): string {
  if (severity === "ok") return t("deploymentsPage.severityOk");
  if (severity === "info") return t("deploymentsPage.severityInfo");
  if (severity === "warning") return t("deploymentsPage.severityWarning");
  if (severity === "critical") return t("deploymentsPage.severityCritical");
  return severity.toUpperCase();
}

function SeverityBadge({ s, t }: { s: string; t: (key: string) => string }) {
  const m: Record<string, { class: string; label: string }> = {
    ok: { class: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300", label: getSeverityLabel("ok", t) },
    info: { class: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300", label: getSeverityLabel("info", t) },
    warning: { class: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300", label: getSeverityLabel("warning", t) },
    critical: { class: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300", label: getSeverityLabel("critical", t) },
  };
  const x = m[s] ?? m.info;
  return (
    <span
      className={cn("py-1 px-2.5 rounded-full font-black text-xs whitespace-nowrap", x.class)}
      title={formatText(t("deploymentsPage.impactSeverityTitle"), { severity: x.label })}
    >
      {x.label}
    </span>
  );
}

function FilterChip({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <a
      href={href}
      className={cn(
        "py-2 px-3 rounded-full border border-border no-underline font-black text-xs",
        active ? "bg-primary text-primary-foreground border-primary" : "bg-card text-foreground"
      )}
    >
      {label}
    </a>
  );
}

function buildHref(base: string, qp: Record<string, string | undefined>, next: Record<string, string | undefined>) {
  const params = new URLSearchParams();
  const merged = { ...qp, ...next };

  for (const [k, v] of Object.entries(merged)) {
    if (v && v !== "all") params.set(k, v);
  }
  const s = params.toString();
  return s ? `${base}?${s}` : base;
}

async function loadOverviewHealth(): Promise<Health | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) return null;
  try {
    const r = await fetch(`${base}/admin/stats/overview?lookback_limit=800`, {
      headers: { "x-admin-key": key },
      cache: "no-store",
    });
    if (!r.ok) return null;
    const data = await r.json();
    return (data?.health as Health) ?? null;
  } catch {
    return null;
  }
}

function healthPillClass(overall?: string) {
  if (overall === "CRIT") return "border border-red-500 text-red-600 dark:text-red-400";
  if (overall === "WARN") return "border border-amber-500 text-amber-600 dark:text-amber-400";
  if (overall === "OK") return "border border-green-500 text-green-600 dark:text-green-400";
  return "border border-slate-400 text-slate-500 dark:text-slate-400";
}

export default async function DeploymentsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; sev?: string; onlyProblems?: string }>;
}) {
  await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);
  const localeTag = locale === "en" ? "en-US" : "tr-TR";

  const health = await loadOverviewHealth();
  const params = await searchParams;
  const statusFilter = params.status ?? "all";
  const sevFilter = params.sev ?? "all";
  const onlyProblems = params.onlyProblems === "1";

  const qp = {
    status: statusFilter,
    sev: sevFilter,
    onlyProblems: onlyProblems ? "1" : undefined,
  };

  const sb = supabaseAdmin();

  let q = sb
    .from("tuning_deployments")
    .select("id,created_at,status,git_sha,rollback_of,title")
    .order("created_at", { ascending: false })
    .limit(80);

  if (!onlyProblems && statusFilter !== "all") {
    q = q.eq("status", statusFilter);
  }

  const { data, error } = await q;

  if (error) {
    return (
      <div className="p-6">
        {formatText(t("deploymentsPage.error"), { message: error.message })}
      </div>
    );
  }

  const guardrails = loadGuardrails();

  const rows: DeploymentWithImpact[] = ((data || []) as DeploymentRow[])
    .map((d): DeploymentWithImpact => {
      const imp = findLatestImpactForDeployment(d.id);
      const sev = imp ? computeSeverity(imp, guardrails) : null;
      return { ...d, _impact: imp, _sev: sev };
    })
    .filter((d) => {
      if (onlyProblems) {
        return d.status === "rolled_back_pending" || d._sev === "critical";
      }
      if (sevFilter !== "all") {
        return d._sev === sevFilter;
      }
      return true;
    });

  const sevRank: Record<string, number> = { critical: 4, warning: 3, info: 2, ok: 1 };

  const sortedRows = [...rows].sort((a, b) => {
    if (onlyProblems) {
      const ra = sevRank[a._sev ?? "info"] ?? 0;
      const rb = sevRank[b._sev ?? "info"] ?? 0;
      if (rb !== ra) return rb - ra;
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const statusOptions = [
    { value: "all", label: t("deploymentsPage.all") },
    { value: "applied", label: t("deploymentsPage.statusApplied") },
    { value: "rolled_back_pending", label: t("deploymentsPage.statusRolledBackPending") },
    { value: "rolled_back", label: t("deploymentsPage.statusRolledBack") },
  ];

  const severityOptions = [
    { value: "all", label: t("deploymentsPage.severityAll") },
    { value: "ok", label: t("deploymentsPage.severityOk") },
    { value: "info", label: t("deploymentsPage.severityInfo") },
    { value: "warning", label: t("deploymentsPage.severityWarning") },
    { value: "critical", label: t("deploymentsPage.severityCritical") },
  ];

  return (
    <div className="p-6 font-sans bg-background text-foreground min-h-screen">
      <div className="max-w-[1400px] mx-auto">
        <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.deployments") }]} />
        <div className="flex items-center gap-2.5">
          <h1 className="text-[26px] font-black m-0">{t("deploymentsPage.title")}</h1>
          {health?.overall && (
            <span className={cn("rounded-full py-1 px-2.5 font-black text-xs", healthPillClass(health.overall))}>
              {t("deploymentsPage.healthLabel")} {health.overall}
            </span>
          )}
        </div>
        <div className="text-muted-foreground mt-1.5">
          {formatText(t("deploymentsPage.subtitle"), { count: sortedRows.length })}
        </div>
        {health && (
          <div className="text-muted-foreground mt-1 text-[13px]">
            {formatText(t("deploymentsPage.statsSummary"), {
              samples: health.samples,
              lowConf: Math.round((health.low_conf_rate ?? 0) * 100),
              highRisk: Math.round((health.high_risk_rate ?? 0) * 100),
            })}
          </div>
        )}

        <div className="mt-3.5 flex gap-2.5 flex-wrap">
          <FilterChip href={buildHref("/admin/deployments", qp, { onlyProblems: "1", status: "all", sev: "all" })} active={onlyProblems} label={t("deploymentsPage.onlyProblems")} />
          <FilterChip href={buildHref("/admin/deployments", qp, { onlyProblems: undefined })} active={!onlyProblems} label={t("deploymentsPage.all")} />
          <span className="ml-2 text-muted-foreground text-xs self-center">{t("deploymentsPage.status")}</span>
          {statusOptions.map((status) => (
            <FilterChip
              key={status.value}
              href={buildHref("/admin/deployments", qp, { status: status.value, onlyProblems: undefined })}
              active={!onlyProblems && statusFilter === status.value}
              label={status.label}
            />
          ))}
          <span className="ml-2 text-muted-foreground text-xs self-center">{t("deploymentsPage.severity")}</span>
          {severityOptions.map((severity) => (
            <FilterChip
              key={severity.value}
              href={buildHref("/admin/deployments", qp, { sev: severity.value, onlyProblems: undefined })}
              active={!onlyProblems && sevFilter === severity.value}
              label={severity.label}
            />
          ))}
        </div>

        {onlyProblems && (
          <div className="mt-3 p-3 rounded-xl border border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/30 font-extrabold text-[13px]">
            {t("deploymentsPage.problemBanner")}
          </div>
        )}

        <div className="mt-3.5 bg-card rounded-2xl border border-border overflow-hidden">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-accent border-b border-border">
                <th className="p-3 text-left font-black text-xs">{t("deploymentsPage.tableDeployed")}</th>
                <th className="p-3 text-left font-black text-xs">{t("deploymentsPage.tableTitle")}</th>
                <th className="p-3 text-left font-black text-xs">{t("deploymentsPage.tableStatus")}</th>
                <th className="p-3 text-left font-black text-xs">{t("deploymentsPage.tableImpact")}</th>
                <th className="p-3 text-left font-black text-xs">{t("deploymentsPage.tableGitSha")}</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((d) => (
                <tr key={d.id} className="border-t border-border">
                  <td className="p-3 text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString(localeTag)}</td>
                  <td className="p-3 text-sm font-bold">{d.title || t("deploymentsPage.untitled")}</td>
                  <td className="p-3 text-xs">
                    <span
                      className={cn(
                        "py-1 px-2 rounded-md font-extrabold",
                        d.status === "rolled_back_pending" && "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
                        d.status === "rolled_back" && "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
                        d.status === "applied" && "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300"
                      )}
                    >
                      {getStatusLabel(d.status ?? "", t)}
                    </span>
                  </td>
                  <td className="p-3">
                    {d._sev ? (
                      <div className="flex gap-2 items-center">
                        <SeverityBadge s={d._sev} t={t} />
                        <a href={`/admin/deployments/${d.id}/impact`} className="font-extrabold text-primary no-underline text-xs">
                          {t("deploymentsPage.viewImpact")}
                        </a>
                      </div>
                    ) : (
                      <span title={t("deploymentsPage.noImpactReport")} className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="p-3 text-[11px] font-mono text-muted-foreground">
                    {typeof d.git_sha === "string" && d.git_sha
                      ? d.git_sha.slice(0, 7)
                      : t("deploymentsPage.noGitSha")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {sortedRows.length === 0 && (
            <div className="p-10 text-center text-muted-foreground">{t("deploymentsPage.noRows")}</div>
          )}
        </div>
      </div>
    </div>
  );
}
