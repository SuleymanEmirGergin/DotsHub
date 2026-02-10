import { requireAdmin } from "@/lib/requireAdmin";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

function loadGuardrails() {
    try {
        const p = path.join(process.cwd(), "..", "config", "tuning_guardrails.json");
        return JSON.parse(fs.readFileSync(p, "utf-8"));
    } catch {
        return null;
    }
}

function buildImpactCommentary(impact: any, guardrails: any) {
    const g = guardrails ?? { thresholds: {}, min_feedback_after: 30 };
    const t = g.thresholds ?? {};

    const minN = Number(g.min_feedback_after ?? 30);
    const downMax = Number(t.down_rate_max_delta ?? 0.15);
    const confMin = Number(t.confidence_decrease_max ?? -0.10);
    const qMax = Number(t.avg_questions_increase_max ?? 1.5);

    const afterTotal = impact?.after?.total ?? 0;

    const d = impact?.delta ?? {};
    const dDown = d.down_rate;
    const dConf = d.avg_confidence;
    const dQ = d.avg_questions;

    const notes: string[] = [];
    const actions: string[] = [];

    if (afterTotal < minN) {
        notes.push(`Yetersiz veri: after feedback sample = ${afterTotal} (< ${minN}). Şimdilik kesin karar yok.`);
        actions.push("Daha fazla kullanıcı geri bildirimi birikmesini bekle (veya internal test ile sample artır).");
        return { severity: "info", notes, actions };
    }

    // Evaluate conditions
    const bad: string[] = [];
    const good: string[] = [];

    if (typeof dDown === "number") {
        if (dDown > downMax) bad.push(`Down-rate kötüleşmiş: Δ=${dDown.toFixed(4)} (limit ${downMax}).`);
        else if (dDown < -0.01) good.push(`Down-rate iyileşmiş: Δ=${dDown.toFixed(4)}.`);
        else notes.push(`Down-rate stabil: Δ=${dDown.toFixed(4)}.`);
    }

    if (typeof dConf === "number") {
        if (dConf < confMin) bad.push(`Confidence düşmüş: Δ=${dConf.toFixed(4)} (limit ${confMin}).`);
        else if (dConf > 0.02) good.push(`Confidence artmış: Δ=${dConf.toFixed(4)}.`);
        else notes.push(`Confidence stabil: Δ=${dConf.toFixed(4)}.`);
    }

    if (typeof dQ === "number") {
        if (dQ > qMax) bad.push(`Soru sayısı artmış: Δ=${dQ.toFixed(3)} (limit ${qMax}).`);
        else if (dQ < -0.15) good.push(`Daha hızlı sonuca gidiyor: Δ=${dQ.toFixed(3)}.`);
        else notes.push(`Soru sayısı stabil: Δ=${dQ.toFixed(3)}.`);
    }

    // Severity
    let severity: "ok" | "warning" | "critical" = "ok";
    if (bad.length >= 2) severity = "critical";
    else if (bad.length === 1) severity = "warning";

    // Compose message
    if (good.length) notes.unshift(...good);
    if (bad.length) notes.unshift(...bad);

    if (severity === "critical") {
        actions.unshift("Rollback önerilir (guardrail zaten tetiklediyse PR'ı merge et).");
    } else if (severity === "warning") {
        actions.unshift("Rollback şart değil; önce hedefli tuning + daha fazla sample ile doğrula.");
    } else {
        actions.unshift("Her şey yolunda görünüyor. Bu deploy'u baseline kabul edip devam et.");
    }

    actions.push("Synonym patch'leri: yanlış eşleşme ihtimali için en çok geçen 5 token'ı replay'den kontrol et.");
    actions.push("Question effectiveness: düşük skor alan soruları demote etmeyi düşün.");

    return { severity, notes, actions };
}

function SevPill({ s }: { s: string }) {
    const m: any = {
        ok: { bg: "#e6fffa", fg: "#065f46", label: "OK" },
        info: { bg: "#eef2ff", fg: "#3730a3", label: "INFO" },
        warning: { bg: "#fff7ed", fg: "#9a3412", label: "WARNING" },
        critical: { bg: "#fee2e2", fg: "#991b1b", label: "CRITICAL" },
    };
    const x = m[s] ?? m.info;
    return (
        <span style={{ padding: "4px 10px", borderRadius: 999, background: x.bg, color: x.fg, fontWeight: 900, fontSize: 12 }}>
            {x.label}
        </span>
    );
}

function Sparkline({ data, label }: { data: number[]; label: string }) {
    if (!data || data.length === 0) return null;

    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    const points = data.map((v, i) => {
        const x = (i / (data.length - 1)) * 100;
        const y = 100 - ((v - min) / range) * 100;
        return `${x},${y}`;
    }).join(" ");

    return (
        <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>{label}</div>
            <svg width="100%" height="40" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ border: "1px solid #eee", borderRadius: 4, background: "#fafafa" }}>
                <polyline
                    points={points}
                    fill="none"
                    stroke="#111"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                />
            </svg>
        </div>
    );
}

export default async function DeploymentImpactPage({ params }: { params: Promise<{ id: string }> }) {
    await requireAdmin();
    const { id } = await params;

    // Load impact report
    let impact = null;
    try {
        const reportsDir = path.join(process.cwd(), "..", "backend", "reports");
        const files = fs
            .readdirSync(reportsDir)
            .filter((f) => f.startsWith(`impact_`) && f.includes(id) && f.endsWith(".json"))
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
            <div style={{ padding: 24 }}>
                <div style={{ maxWidth: 900, margin: "0 auto" }}>
                    <h1 style={{ fontSize: 26, fontWeight: 900 }}>Impact Report</h1>
                    <div style={{ marginTop: 14, padding: 20, background: "#fee2e2", borderRadius: 12, color: "#991b1b" }}>
                        No impact report found for deployment {id}
                    </div>
                    <div style={{ marginTop: 14 }}>
                        <a href="/admin/deployments" style={{ fontWeight: 800, color: "#111" }}>← Back to deployments</a>
                    </div>
                </div>
            </div>
        );
    }

    const guardrails = loadGuardrails();
    const commentary = buildImpactCommentary(impact, guardrails);

    const before = impact.before ?? {};
    const after = impact.after ?? {};
    const delta = impact.delta ?? {};

    // Extract sparkline data from daily series
    const dailySeries = after.daily_series || [];
    const downRateSeries = dailySeries.map((d: any) => d.down_rate ?? 0);
    const confSeries = dailySeries.map((d: any) => d.confidence ?? 0);

    return (
        <div style={{ padding: 24, fontFamily: "ui-sans-serif", background: "#fafafa", minHeight: "100vh" }}>
            <div style={{ maxWidth: 1000, margin: "0 auto" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                        <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Impact Report</h1>
                        <div style={{ color: "#666", marginTop: 4, fontSize: 13 }}>Deployment: {id}</div>
                    </div>
                    <a href="/admin/deployments" style={{ fontWeight: 800, color: "#111", textDecoration: "none" }}>
                        ← Deployments
                    </a>
                </div>

                {/* Impact Commentary */}
                <div style={{ marginTop: 14, border: "1px solid #eee", borderRadius: 16, padding: 16, background: "white" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ fontWeight: 900, fontSize: 16 }}>Impact Commentary</div>
                        <SevPill s={commentary.severity} />
                    </div>

                    <div style={{ marginTop: 10, color: "#111" }}>
                        <div style={{ fontSize: 12, color: "#666" }}>Findings</div>
                        <ul style={{ marginTop: 8, paddingLeft: 18 }}>
                            {commentary.notes.map((x: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{x}</li>)}
                        </ul>

                        <div style={{ fontSize: 12, color: "#666", marginTop: 10 }}>Recommended actions</div>
                        <ol style={{ marginTop: 8, paddingLeft: 18 }}>
                            {commentary.actions.map((x: string, i: number) => <li key={i} style={{ marginBottom: 6 }}>{x}</li>)}
                        </ol>
                    </div>
                </div>

                {/* Metrics Grid */}
                <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>SAMPLE SIZE</div>
                        <div style={{ marginTop: 8, fontSize: 24, fontWeight: 900 }}>
                            {before.total ?? 0} → {after.total ?? 0}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 12, color: "#666" }}>
                            Δ {((after.total ?? 0) - (before.total ?? 0)) >= 0 ? "+" : ""}{((after.total ?? 0) - (before.total ?? 0))}
                        </div>
                    </div>

                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>DOWN-RATE</div>
                        <div style={{ marginTop: 8, fontSize: 24, fontWeight: 900 }}>
                            {((before.down_rate ?? 0) * 100).toFixed(1)}% → {((after.down_rate ?? 0) * 100).toFixed(1)}%
                        </div>
                        <div style={{ marginTop: 4, fontSize: 12, color: delta.down_rate > 0 ? "#991b1b" : "#065f46" }}>
                            Δ {delta.down_rate >= 0 ? "+" : ""}{((delta.down_rate ?? 0) * 100).toFixed(2)}%
                        </div>
                        <Sparkline data={downRateSeries} label="Last 7 days" />
                    </div>

                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>AVG CONFIDENCE</div>
                        <div style={{ marginTop: 8, fontSize: 24, fontWeight: 900 }}>
                            {(before.avg_confidence ?? 0).toFixed(3)} → {(after.avg_confidence ?? 0).toFixed(3)}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 12, color: delta.avg_confidence >= 0 ? "#065f46" : "#991b1b" }}>
                            Δ {delta.avg_confidence >= 0 ? "+" : ""}{(delta.avg_confidence ?? 0).toFixed(4)}
                        </div>
                        <Sparkline data={confSeries} label="Last 7 days" />
                    </div>

                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>AVG QUESTIONS</div>
                        <div style={{ marginTop: 8, fontSize: 24, fontWeight: 900 }}>
                            {(before.avg_questions ?? 0).toFixed(1)} → {(after.avg_questions ?? 0).toFixed(1)}
                        </div>
                        <div style={{ marginTop: 4, fontSize: 12, color: delta.avg_questions <= 0 ? "#065f46" : "#991b1b" }}>
                            Δ {delta.avg_questions >= 0 ? "+" : ""}{(delta.avg_questions ?? 0).toFixed(2)}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
