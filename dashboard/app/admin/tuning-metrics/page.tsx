import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

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

function Sparkline({ data, color }: { data: number[]; color?: string }) {
    if (!data || data.length === 0) return <span style={{ color: "#9ca3af" }}>—</span>;

    const max = Math.max(...data, 0.01);
    const min = Math.min(...data, 0);
    const range = max - min || 0.01;

    const points = data.map((v, i) => {
        const x = (i / Math.max(1, data.length - 1)) * 60;
        const y = 20 - ((v - min) / range) * 18;
        return `${x},${y}`;
    }).join(" ");

    return (
        <svg width="64" height="20" style={{ display: "inline-block", verticalAlign: "middle" }}>
            <polyline
                points={points}
                fill="none"
                stroke={color || "#111"}
                strokeWidth="1.5"
            />
        </svg>
    );
}

export default async function TuningMetricsPage() {
    await requireAdmin();

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

    return (
        <div style={{ padding: 24, fontFamily: "ui-sans-serif", background: "#fafafa", minHeight: "100vh" }}>
            <div style={{ maxWidth: 1400, margin: "0 auto" }}>
                <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Tuning Metrics</h1>
                <div style={{ color: "#666", marginTop: 6 }}>
                    System performance & question effectiveness
                </div>

                {/* KPIs */}
                <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>SESSIONS (RECENT)</div>
                        <div style={{ marginTop: 8, fontSize: 32, fontWeight: 900 }}>{totalSessions}</div>
                    </div>

                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>AVG CONFIDENCE</div>
                        <div style={{ marginTop: 8, fontSize: 32, fontWeight: 900 }}>{avgConf.toFixed(3)}</div>
                    </div>

                    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, background: "white" }}>
                        <div style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>AVG QUESTIONS</div>
                        <div style={{ marginTop: 8, fontSize: 32, fontWeight: 900 }}>{avgQuestions.toFixed(1)}</div>
                    </div>
                </div>

                {/* Question Effectiveness Table */}
                <div style={{ marginTop: 20 }}>
                    <h2 style={{ fontSize: 18, fontWeight: 900, margin: 0 }}>Question Effectiveness</h2>
                    <div style={{ color: "#666", marginTop: 4, fontSize: 13 }}>
                        {effectiveness ? `Report generated: ${new Date(effectiveness.generated_at).toLocaleString()}` : "No report available"}
                    </div>
                </div>

                {questions.length > 0 ? (
                    <div style={{ marginTop: 14, background: "white", borderRadius: 16, border: "1px solid #eee", overflow: "hidden" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                            <thead>
                                <tr style={{ background: "#f9fafb", borderBottom: "1px solid #eee" }}>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Question</th>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Asked</th>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Effectiveness</th>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Gap Δ</th>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Conf Δ</th>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Balance</th>
                                    <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Trend</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedQuestions.slice(0, 50).map((q: any) => {
                                    const eff = q.effectiveness_0_1 ?? 0;
                                    const color = eff >= 0.6 ? "#065f46" : eff >= 0.4 ? "#9a3412" : "#991b1b";

                                    // Mock trend data (in real app, this comes from historical reports)
                                    const trendData = [eff * 0.9, eff * 0.95, eff, eff * 1.02, eff * 1.01];

                                    return (
                                        <tr key={q.canonical} style={{ borderTop: "1px solid #f3f4f6" }}>
                                            <td style={{ padding: 12, fontSize: 13, fontWeight: 700 }}>
                                                {q.canonical}
                                            </td>
                                            <td style={{ padding: 12, fontSize: 12, color: "#666" }}>
                                                {q.asked_count}
                                            </td>
                                            <td style={{ padding: 12, fontSize: 13, fontWeight: 900, color }}>
                                                {(eff * 100).toFixed(1)}%
                                            </td>
                                            <td style={{ padding: 12, fontSize: 12, color: q.avg_gap_delta > 0 ? "#065f46" : "#666" }}>
                                                {q.avg_gap_delta ? `+${q.avg_gap_delta.toFixed(3)}` : "—"}
                                            </td>
                                            <td style={{ padding: 12, fontSize: 12, color: q.avg_conf_delta > 0 ? "#065f46" : "#666" }}>
                                                {q.avg_conf_delta ? `+${q.avg_conf_delta.toFixed(3)}` : "—"}
                                            </td>
                                            <td style={{ padding: 12, fontSize: 12 }}>
                                                {q.balance_0_1 ? (q.balance_0_1 * 100).toFixed(0) + "%" : "—"}
                                            </td>
                                            <td style={{ padding: 12 }}>
                                                <Sparkline data={trendData} color={color} />
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div style={{ marginTop: 14, padding: 40, textAlign: "center", color: "#9ca3af", background: "white", borderRadius: 16, border: "1px solid #eee" }}>
                        No effectiveness data available. Run question_effectiveness_report.py to generate.
                    </div>
                )}
            </div>
        </div>
    );
}
