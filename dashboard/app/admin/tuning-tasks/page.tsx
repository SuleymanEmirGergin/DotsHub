import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";

export const dynamic = "force-dynamic";

function Pill({ text, color }: { text: string; color?: string }) {
    const bg = color === "high" ? "#fee2e2" : color === "medium" ? "#fff7ed" : "#f3f4f6";
    const fg = color === "high" ? "#991b1b" : color === "medium" ? "#9a3412" : "#374151";

    return (
        <span style={{ display: "inline-block", padding: "4px 10px", borderRadius: 999, background: bg, color: fg, fontSize: 12, fontWeight: 700 }}>
            {text}
        </span>
    );
}

function StatusBadge({ status }: { status: string }) {
    const colors: Record<string, { bg: string; fg: string }> = {
        open: { bg: "#eef2ff", fg: "#3730a3" },
        accepted: { bg: "#e6fffa", fg: "#065f46" },
        rejected: { bg: "#fee2e2", fg: "#991b1b" },
        done: { bg: "#f3f4f6", fg: "#374151" },
    };
    const c = colors[status] || colors.open;

    return (
        <span style={{ padding: "4px 10px", borderRadius: 999, background: c.bg, color: c.fg, fontWeight: 900, fontSize: 12 }}>
            {status.toUpperCase()}
        </span>
    );
}

export default async function TuningTasksPage({
    searchParams,
}: {
    searchParams: Promise<{ status?: string; type?: string }>;
}) {
    await requireAdmin();
    const params = await searchParams;
    const statusFilter = params.status ?? "all";
    const typeFilter = params.type ?? "all";

    const sb = supabaseAdmin();

    let q = sb
        .from("tuning_tasks")
        .select("id,created_at,task_type,severity,title,description,status,session_id,patch")
        .order("created_at", { ascending: false })
        .limit(100);

    if (statusFilter !== "all") {
        q = q.eq("status", statusFilter);
    }
    if (typeFilter !== "all") {
        q = q.eq("task_type", typeFilter);
    }

    const { data: tasks, error } = await q;

    if (error) return <div style={{ padding: 24 }}>Error: {error.message}</div>;

    const taskCount = tasks?.length ?? 0;

    return (
        <div style={{ padding: 24, fontFamily: "ui-sans-serif", background: "#fafafa", minHeight: "100vh" }}>
            <div style={{ maxWidth: 1400, margin: "0 auto" }}>
                <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Tuning Tasks</h1>
                <div style={{ color: "#666", marginTop: 6 }}>
                    Auto-generated improvement tasks • showing <b>{taskCount}</b>
                </div>

                {/* Filters */}
                <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <span style={{ color: "#666", fontSize: 12, alignSelf: "center" }}>Status:</span>
                    {["all", "open", "accepted", "rejected", "done"].map((s) => (
                        <a
                            key={s}
                            href={`/admin/tuning-tasks?status=${s}${typeFilter !== "all" ? `&type=${typeFilter}` : ""}`}
                            style={{
                                padding: "6px 12px",
                                borderRadius: 999,
                                border: "1px solid #eee",
                                background: statusFilter === s ? "#111" : "white",
                                color: statusFilter === s ? "white" : "#111",
                                fontWeight: 800,
                                textDecoration: "none",
                                fontSize: 12,
                            }}
                        >
                            {s}
                        </a>
                    ))}

                    <span style={{ marginLeft: 8, color: "#666", fontSize: 12, alignSelf: "center" }}>Type:</span>
                    {["all", "KEYWORD_MISSING", "SPECIALTY_CONFUSION", "QUESTION_WEAKNESS"].map((t) => (
                        <a
                            key={t}
                            href={`/admin/tuning-tasks?type=${t}${statusFilter !== "all" ? `&status=${statusFilter}` : ""}`}
                            style={{
                                padding: "6px 12px",
                                borderRadius: 999,
                                border: "1px solid #eee",
                                background: typeFilter === t ? "#111" : "white",
                                color: typeFilter === t ? "white" : "#111",
                                fontWeight: 800,
                                textDecoration: "none",
                                fontSize: 12,
                            }}
                        >
                            {t === "all" ? "all" : t.replace(/_/g, " ")}
                        </a>
                    ))}
                </div>

                {/* Table */}
                <div style={{ marginTop: 14, background: "white", borderRadius: 16, border: "1px solid #eee", overflow: "hidden" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                            <tr style={{ background: "#f9fafb", borderBottom: "1px solid #eee" }}>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Created</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Type</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Title</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Severity</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Status</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Patch</th>
                                <th style={{ padding: 12, textAlign: "left", fontWeight: 900, fontSize: 12 }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(tasks || []).map((task) => {
                                const hasPatch = task.patch && Object.keys(task.patch).length > 0;

                                return (
                                    <tr key={task.id} style={{ borderTop: "1px solid #f3f4f6" }}>
                                        <td style={{ padding: 12, fontSize: 12, color: "#666" }}>
                                            {new Date(task.created_at).toLocaleDateString()}
                                        </td>
                                        <td style={{ padding: 12, fontSize: 12 }}>
                                            {task.task_type.replace(/_/g, " ")}
                                        </td>
                                        <td style={{ padding: 12, fontSize: 14, fontWeight: 700 }}>
                                            {task.title}
                                            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
                                                {task.description.slice(0, 80)}...
                                            </div>
                                        </td>
                                        <td style={{ padding: 12 }}>
                                            <Pill text={task.severity} color={task.severity} />
                                        </td>
                                        <td style={{ padding: 12 }}>
                                            <StatusBadge status={task.status} />
                                        </td>
                                        <td style={{ padding: 12, fontSize: 12 }}>
                                            {hasPatch ? (
                                                <span style={{ color: "#065f46" }}>✓ Generated</span>
                                            ) : (
                                                <span style={{ color: "#9ca3af" }}>—</span>
                                            )}
                                        </td>
                                        <td style={{ padding: 12 }}>
                                            <div style={{ display: "flex", gap: 8 }}>
                                                {task.session_id && (
                                                    <a
                                                        href={`/admin/sessions/${task.session_id}/replay`}
                                                        style={{ fontSize: 12, fontWeight: 800, color: "#111", textDecoration: "none" }}
                                                    >
                                                        Replay
                                                    </a>
                                                )}
                                                {!hasPatch && task.status === "open" && (
                                                    <button
                                                        onClick={() => fetch(`/v1/admin/tuning-tasks/${task.id}/generate-patch`, { method: "POST" }).then(() => location.reload())}
                                                        style={{ fontSize: 12, fontWeight: 800, background: "#111", color: "white", border: "none", padding: "4px 8px", borderRadius: 6, cursor: "pointer" }}
                                                    >
                                                        Generate Patch
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>

                    {taskCount === 0 && (
                        <div style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>
                            No tuning tasks found
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
