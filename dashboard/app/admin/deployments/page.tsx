import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

type Health = {
    overall: "INFO" | "OK" | "WARN" | "CRIT";
    samples: number;
    low_conf_rate: number;
    high_risk_rate: number;
};

function loadGuardrails() {
    try {
        const p = path.join(process.cwd(), "..", "config", "tuning_guardrails.json");
        return JSON.parse(fs.readFileSync(p, "utf-8"));
    } catch {
        return null;
    }
}

function findLatestImpactForDeployment(deploymentId: string) {
    try {
        const reportsDir = path.join(process.cwd(), "..", "backend", "reports");
        if (!fs.existsSync(reportsDir)) return null;

        const files = fs
            .readdirSync(reportsDir)
            .filter((f) => f.startsWith(`impact_`) && f.includes(deploymentId) && f.endsWith(".json"))
            .sort();
        if (files.length === 0) return null;

        const latest = files[files.length - 1];
        const p = path.join(reportsDir, latest);
        return JSON.parse(fs.readFileSync(p, "utf-8"));
    } catch {
        return null;
    }
}

function computeSeverity(impact: any, guardrails: any): "info" | "ok" | "warning" | "critical" {
    const g = guardrails ?? { thresholds: {}, min_feedback_after: 30 };
    const t = g.thresholds ?? {};

    const minN = Number(g.min_feedback_after ?? 30);
    const downMax = Number(t.down_rate_max_delta ?? 0.15);
    const confMin = Number(t.confidence_decrease_max ?? -0.10);
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

function SeverityBadge({ s }: { s: string }) {
    const m: Record<string, { bg: string; fg: string; label: string }> = {
        ok: { bg: "#e6fffa", fg: "#065f46", label: "OK" },
        info: { bg: "#eef2ff", fg: "#3730a3", label: "INFO" },
        warning: { bg: "#fff7ed", fg: "#9a3412", label: "WARN" },
        critical: { bg: "#fee2e2", fg: "#991b1b", label: "CRIT" },
    };
    const x = m[s] ?? m.info;
    return (
        <span
            style={{
                padding: "4px 10px",
                borderRadius: 999,
                background: x.bg,
                color: x.fg,
                fontWeight: 900,
                fontSize: 12,
                whiteSpace: "nowrap",
            }}
            title={`Impact severity: ${x.label}`}
        >
            {x.label}
        </span>
    );
}

function FilterChip({ href, active, label }: { href: string; active: boolean; label: string }) {
    return (
        <a
            href={href}
            style={{
                padding: "8px 12px",
                borderRadius: 999,
                border: "1px solid var(--dash-border)",
                background: active ? "var(--dash-accent)" : "var(--dash-bg-card)",
                color: active ? "var(--dash-bg)" : "var(--dash-text)",
                fontWeight: 900,
                textDecoration: "none",
                fontSize: 12,
            }}
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

function healthPillStyle(overall?: string) {
    if (overall === "CRIT") return { border: "1px solid #ef4444", color: "#dc2626" };
    if (overall === "WARN") return { border: "1px solid #f59e0b", color: "#d97706" };
    if (overall === "OK") return { border: "1px solid #22c55e", color: "#16a34a" };
    return { border: "1px solid #94a3b8", color: "#64748b" };
}

export default async function DeploymentsPage({
    searchParams,
}: {
    searchParams: Promise<{ status?: string; sev?: string; onlyProblems?: string }>;
}) {
    await requireAdmin();
    const health = await loadOverviewHealth();
    const params = await searchParams;
    const statusFilter = params.status ?? "all";
    const sevFilter = params.sev ?? "all";
    const onlyProblems = params.onlyProblems === "1";

    const qp = { status: statusFilter, sev: sevFilter, onlyProblems: onlyProblems ? "1" : undefined };

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

    if (error) return <div style={{ padding: 24 }}>Error: {error.message}</div>;

    const guardrails = loadGuardrails();

    const rows = (data || []).map((d: any) => {
        const imp = findLatestImpactForDeployment(d.id);
        const sev = imp ? computeSeverity(imp, guardrails) : null;
        return { ...d, _impact: imp, _sev: sev };
    }).filter((d: any) => {
        if (onlyProblems) {
            return d.status === "rolled_back_pending" || d._sev === "critical";
        }
        if (sevFilter !== "all") {
            return d._sev === sevFilter;
        }
        return true;
    });

    // Sort by severity when onlyProblems, otherwise newest first
    const sevRank: Record<string, number> = { critical: 4, warning: 3, info: 2, ok: 1 };

    const sortedRows = [...rows].sort((a: any, b: any) => {
        if (onlyProblems) {
            const ra = sevRank[a._sev ?? "info"] ?? 0;
            const rb = sevRank[b._sev ?? "info"] ?? 0;
            if (rb !== ra) return rb - ra; // severity desc
        }
        // fallback: newest first
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

    return (
        <div style={{ padding: 24, fontFamily: "ui-sans-serif", background: "var(--dash-bg)", color: "var(--dash-text)", minHeight: "100vh" }}>
            <div style={{ maxWidth: 1400, margin: "0 auto" }}>
                <Breadcrumb items={[{ label: "Admin", href: "/admin/sessions" }, { label: "Deployments" }]} />
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Deployments</h1>
                    {health?.overall && (
                        <span
                            style={{
                                ...healthPillStyle(health.overall),
                                borderRadius: 999,
                                padding: "4px 10px",
                                fontWeight: 900,
                                fontSize: 12,
                            }}
                        >
                            HEALTH {health.overall}
                        </span>
                    )}
                </div>
                <div style={{ color: "var(--dash-text-muted)", marginTop: 6 }}>
                    Auto tuning & rollback history • showing <b>{sortedRows.length}</b>
                </div>
                {health && (
                    <div style={{ color: "var(--dash-text-muted)", marginTop: 4, fontSize: 13 }}>
                        samples: {health.samples} • low_conf: {Math.round((health.low_conf_rate ?? 0) * 100)}% • high_risk: {Math.round((health.high_risk_rate ?? 0) * 100)}%
                    </div>
                )}

                {/* Filters */}
                <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <FilterChip
                        href={buildHref("/admin/deployments", qp, { onlyProblems: "1", status: "all", sev: "all" })}
                        active={onlyProblems}
                        label="Only problems"
                    />
                    <FilterChip
                        href={buildHref("/admin/deployments", qp, { onlyProblems: undefined })}
                        active={!onlyProblems}
                        label="All"
                    />

                    <span style={{ marginLeft: 8, color: "var(--dash-text-muted)", fontSize: 12, alignSelf: "center" }}>Status:</span>
                    {["all", "applied", "rolled_back_pending", "rolled_back"].map((s) => (
                        <FilterChip
                            key={s}
                            href={buildHref("/admin/deployments", qp, { status: s, onlyProblems: undefined })}
                            active={!onlyProblems && statusFilter === s}
                            label={s}
                        />
                    ))}

                    <span style={{ marginLeft: 8, color: "var(--dash-text-muted)", fontSize: 12, alignSelf: "center" }}>Severity:</span>
                    {["all", "ok", "info", "warning", "critical"].map((s) => (
                        <FilterChip
                            key={s}
                            href={buildHref("/admin/deployments", qp, { sev: s, onlyProblems: undefined })}
                            active={!onlyProblems && sevFilter === s}
                            label={s.toUpperCase()}
                        />
                    ))}
                </div>

                {/* Problem Banner */}
                {onlyProblems && (
                    <div style={{ marginTop: 12, padding: 12, borderRadius: 14, border: "1px solid #fee2e2", background: "#fff1f2", fontWeight: 800, fontSize: 13 }}>
                        Showing only problematic deployments (rolled_back_pending OR CRITICAL). Sorted by severity.
                    </div>
                )}

                {/* Table */}
                <div style={{ marginTop: 14, background: "var(--dash-bg-card)", borderRadius: 16, border: "1px solid var(--dash-border)", overflow: "hidden" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                            <tr style={{ background: "var(--dash-accent-bg)", borderBottom: "1px solid var(--dash-border)" }}>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Deployed</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Title</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Status</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Impact</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Git SHA</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sortedRows.map((d: any) => (
                                <tr key={d.id} style={{ borderTop: "1px solid var(--dash-border)" }}>
                                    <td style={{ padding: 12, fontSize: 12, color: "var(--dash-text-muted)" }}>
                                        {new Date(d.created_at).toLocaleString()}
                                    </td>
                                    <td style={{ padding: 12, fontSize: 14, fontWeight: 700 }}>
                                        {d.title || "Untitled"}
                                    </td>
                                    <td style={{ padding: 12, fontSize: 12 }}>
                                        <span
                                            style={{
                                                padding: "4px 8px",
                                                borderRadius: 6,
                                                background: d.status === "rolled_back_pending" ? "#fee2e2" : d.status === "rolled_back" ? "#f3f4f6" : "#e6fffa",
                                                color: d.status === "rolled_back_pending" ? "#991b1b" : d.status === "rolled_back" ? "#374151" : "#065f46",
                                                fontWeight: 800,
                                            }}
                                        >
                                            {d.status}
                                        </span>
                                    </td>
                                    <td style={{ padding: 12 }}>
                                        {d._sev ? (
                                            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                                                <SeverityBadge s={d._sev} />
                                                <a href={`/admin/deployments/${d.id}/impact`} style={{ fontWeight: 800, color: "var(--dash-accent)", textDecoration: "none", fontSize: 12 }}>
                                                    View →
                                                </a>
                                            </div>
                                        ) : (
                                            <span title="No impact report found" style={{ color: "#9ca3af" }}>—</span>
                                        )}
                                    </td>
                                    <td style={{ padding: 12, fontSize: 11, fontFamily: "monospace", color: "var(--dash-text-muted)" }}>
                                        {d.git_sha ? d.git_sha.slice(0, 7) : "—"}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {sortedRows.length === 0 && (
                        <div style={{ padding: 40, textAlign: "center", color: "var(--dash-text-muted)" }}>
                            No deployments found
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
