import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

function Pill({ text, color }: { text: string; color?: string }) {
  const cls = cn(
    "inline-block py-1 px-2.5 rounded-full text-xs font-bold",
    color === "high" && "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    color === "medium" && "bg-amber-50 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    (!color || color !== "high" && color !== "medium") && "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
  );
  return <span className={cls}>{text}</span>;
}

function StatusBadge({ status }: { status: string }) {
  const cls = cn(
    "py-1 px-2.5 rounded-full font-black text-xs",
    status === "open" && "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
    status === "accepted" && "bg-teal-50 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
    status === "rejected" && "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    status === "done" && "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    !["open", "accepted", "rejected", "done"].includes(status) && "bg-indigo-100 text-indigo-800"
  );
  return <span className={cls}>{status.toUpperCase()}</span>;
}

const TUNING_SORT_COLUMNS = ["created_at", "task_type", "title", "status"] as const;

function tuningTableHref(params: { status?: string; type?: string; sort?: string; order?: string }, col: string) {
    const nextOrder = params.sort === col && params.order === "desc" ? "asc" : "desc";
    const sp = new URLSearchParams();
    if (params.status && params.status !== "all") sp.set("status", params.status);
    if (params.type && params.type !== "all") sp.set("type", params.type);
    sp.set("sort", col);
    sp.set("order", nextOrder);
    const s = sp.toString();
    return s ? `/admin/tuning-tasks?${s}` : "/admin/tuning-tasks";
}

export default async function TuningTasksPage({
    searchParams,
}: {
    searchParams: Promise<{ status?: string; type?: string; sort?: string; order?: string }>;
}) {
    await requireAdmin();
    const params = await searchParams;
    const statusFilter = params.status ?? "all";
    const typeFilter = params.type ?? "all";
    const sortCol: (typeof TUNING_SORT_COLUMNS)[number] = TUNING_SORT_COLUMNS.includes(params.sort as any)
        ? (params.sort as (typeof TUNING_SORT_COLUMNS)[number])
        : "created_at";
    const ascending = params.order === "asc";

    const sb = supabaseAdmin();

    let q = sb
        .from("tuning_tasks")
        .select("id,created_at,task_type,severity,title,description,status,session_id,patch")
        .order(sortCol, { ascending })
        .limit(100);

    if (statusFilter !== "all") {
        q = q.eq("status", statusFilter);
    }
    if (typeFilter !== "all") {
        q = q.eq("task_type", typeFilter);
    }

    const { data: tasks, error } = await q;

    const locale = await getLocale();

    if (error) return <div className="p-6">{getText(locale, "common.error")}: {error.message}</div>;

    const taskCount = tasks?.length ?? 0;

    return (
        <div className="p-6 bg-background text-foreground min-h-screen font-sans">
            <div className="max-w-[1400px] mx-auto">
                <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.tuningTasks") }]} />
                <h1 className="text-[26px] font-black m-0">{getText(locale, "tuningTasks.title")}</h1>
                <div className="text-muted-foreground mt-1.5">
                    {getText(locale, "tuningTasks.subtitle")} <b>{taskCount}</b>
                    {" · "}
                    <a href="/api/admin/export/tuning-tasks" download className="text-primary font-bold no-underline hover:underline">{getText(locale, "tuningTasks.exportCsv")}</a>
                </div>

                <div className="mt-3.5 flex gap-2.5 flex-wrap items-center">
                    <span className="text-muted-foreground text-xs">{getText(locale, "tuningTasks.statusLabel")}</span>
                    {["all", "open", "accepted", "rejected", "done"].map((s) => (
                        <a
                            key={s}
                            href={`/admin/tuning-tasks?status=${s}${typeFilter !== "all" ? `&type=${typeFilter}` : ""}`}
                            className={cn(
                                "py-1.5 px-3 rounded-full border border-border no-underline font-extrabold text-xs",
                                statusFilter === s ? "bg-primary text-primary-foreground" : "bg-card text-foreground"
                            )}
                        >
                            {s}
                        </a>
                    ))}
                    <span className="ml-2 text-muted-foreground text-xs">{getText(locale, "tuningTasks.typeLabel")}</span>
                    {["all", "KEYWORD_MISSING", "SPECIALTY_CONFUSION", "QUESTION_WEAKNESS"].map((t) => (
                        <a
                            key={t}
                            href={`/admin/tuning-tasks?type=${t}${statusFilter !== "all" ? `&status=${statusFilter}` : ""}`}
                            className={cn(
                                "py-1.5 px-3 rounded-full border border-border no-underline font-extrabold text-xs",
                                typeFilter === t ? "bg-primary text-primary-foreground" : "bg-card text-foreground"
                            )}
                        >
                            {t === "all" ? "all" : t.replace(/_/g, " ")}
                        </a>
                    ))}
                </div>

                <div className="mt-3.5 bg-card rounded-2xl border border-border overflow-hidden">
                    <table className="w-full border-collapse">
                        <thead>
                            <tr className="bg-accent border-b border-border">
                                <th className="p-3 text-left font-black text-xs">
                                    <a href={tuningTableHref(params, "created_at")} className="text-primary no-underline hover:underline">{getText(locale, "tuningTasks.columnCreated")} {sortCol === "created_at" && (ascending ? "↑" : "↓")}</a>
                                </th>
                                <th className="p-3 text-left font-black text-xs">
                                    <a href={tuningTableHref(params, "task_type")} className="text-primary no-underline hover:underline">{getText(locale, "tuningTasks.columnType")} {sortCol === "task_type" && (ascending ? "↑" : "↓")}</a>
                                </th>
                                <th className="p-3 text-left font-black text-xs">
                                    <a href={tuningTableHref(params, "title")} className="text-primary no-underline hover:underline">{getText(locale, "tuningTasks.columnTitle")} {sortCol === "title" && (ascending ? "↑" : "↓")}</a>
                                </th>
                                <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningTasks.severity")}</th>
                                <th className="p-3 text-left font-black text-xs">
                                    <a href={tuningTableHref(params, "status")} className="text-primary no-underline hover:underline">{getText(locale, "tuningTasks.columnStatus")} {sortCol === "status" && (ascending ? "↑" : "↓")}</a>
                                </th>
                                <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningTasks.patch")}</th>
                                <th className="p-3 text-left font-black text-xs">{getText(locale, "tuningTasks.actions")}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(tasks || []).map((task) => {
                                const hasPatch = task.patch && Object.keys(task.patch).length > 0;
                                return (
                                    <tr key={task.id} className="border-t border-border">
                                        <td className="p-3 text-xs text-muted-foreground">{new Date(task.created_at).toLocaleDateString()}</td>
                                        <td className="p-3 text-xs">{task.task_type.replace(/_/g, " ")}</td>
                                        <td className="p-3 text-sm font-bold">
                                            {task.title}
                                            <div className="text-xs text-muted-foreground mt-1">{task.description.slice(0, 80)}...</div>
                                        </td>
                                        <td className="p-3"><Pill text={task.severity} color={task.severity} /></td>
                                        <td className="p-3"><StatusBadge status={task.status} /></td>
                                        <td className="p-3 text-xs">
                                            {hasPatch ? <span className="text-teal-700 dark:text-teal-400">✓ {getText(locale, "tuningTasks.generated")}</span> : <span className="text-gray-400">—</span>}
                                        </td>
                                        <td className="p-3">
                                            <div className="flex gap-2">
                                                {task.session_id && (
                                                    <a href={`/admin/sessions/${task.session_id}/replay`} className="text-xs font-extrabold text-foreground no-underline hover:underline">
                                                        {getText(locale, "tuningTasks.replay")}
                                                    </a>
                                                )}
                                                {!hasPatch && task.status === "open" && (
                                                    <button
                                                        onClick={() => fetch(`/api/admin/tuning-tasks/${task.id}/generate-patch`, { method: "POST" }).then(() => location.reload())}
                                                        className="text-xs font-extrabold bg-primary text-primary-foreground border-none py-1 px-2 rounded-md cursor-pointer hover:opacity-90"
                                                    >
                                                        {getText(locale, "tuningTasks.generatePatch")}
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
                        <div className="p-10 text-center text-muted-foreground">{getText(locale, "tuningTasks.noTasks")}</div>
                    )}
                </div>
            </div>
        </div>
    );
}
