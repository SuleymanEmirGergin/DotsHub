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

const SORT_COLUMNS = ["created_at", "envelope_type", "recommended_specialty_tr", "confidence_label_tr", "stop_reason"] as const;

function sessionsTableHref(params: { feedback?: string; sort?: string; order?: string }, col: string) {
  const nextOrder = params.sort === col && params.order === "desc" ? "asc" : "desc";
  const sp = new URLSearchParams();
  if (params.feedback) sp.set("feedback", params.feedback);
  sp.set("sort", col);
  sp.set("order", nextOrder);
  return `/admin/sessions?${sp.toString()}`;
}

export default async function SessionsPage({
  searchParams,
}: {
  searchParams: Promise<{ feedback?: string; sort?: string; order?: string }>;
}) {
  await requireAdmin();
  const locale = await getLocale();
  const params = await searchParams;
  const { feedback: feedbackFilter, sort: sortCol, order: orderDir } = params;
  const sort: (typeof SORT_COLUMNS)[number] = SORT_COLUMNS.includes(sortCol as (typeof SORT_COLUMNS)[number])
    ? (sortCol as (typeof SORT_COLUMNS)[number])
    : "created_at";
  const ascending = orderDir === "asc";

  // Use admin client for data fetching (RLS bypass, works without auth
  // setup). Throws SupabaseEnvMissingError when env vars aren't set
  // (localhost Playwright CI). Catch that specific case and render an
  // empty "Sessions" state — beats crashing into not-found.
  let sb: ReturnType<typeof supabaseAdmin>;
  try {
    sb = supabaseAdmin();
  } catch {
    return (
      <div className="p-6 max-w-[1200px] mx-auto bg-background text-foreground">
        <h1 className="text-2xl font-bold mb-4">Sessions</h1>
        <p className="text-muted-foreground">
          {getText(locale, "common.error")}: Supabase env not configured.
        </p>
      </div>
    );
  }

  // Feedback filter: find session_ids with matching feedback rating
  let sessionIds: string[] | null = null;

  if (feedbackFilter === "down" || feedbackFilter === "up") {
    const { data: fb } = await sb
      .from("triage_feedback")
      .select("session_id,rating")
      .eq("rating", feedbackFilter)
      .order("created_at", { ascending: false })
      .limit(500);

    sessionIds = Array.from(
      new Set((fb ?? []).map((x: any) => x.session_id).filter(Boolean)),
    );
    if (sessionIds.length === 0) {
      sessionIds = ["00000000-0000-0000-0000-000000000000"];
    }
  }

  let q = sb
    .from("triage_sessions")
    .select(
      "id,created_at,envelope_type,recommended_specialty_tr,confidence_label_tr,confidence_0_1,stop_reason",
    )
    .order(sort, { ascending })
    .limit(100);

  if (sessionIds) q = q.in("id", sessionIds);

  const { data, error } = await q;

  if (error) return <div className="p-6">{getText(locale, "common.error")}: {error.message}</div>;

  return (
    <div className="p-6 max-w-[1200px] mx-auto bg-background text-foreground">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.sessions") }]} />
      <div className="flex justify-between items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold m-0">{getText(locale, "sessions.title")}</h1>
          <p className="text-muted-foreground mt-1.5">
            {getText(locale, "sessions.last100")}
            {feedbackFilter ? ` \u2022 ${getText(locale, "sessions.filterFeedback")}=${feedbackFilter}` : ""}
          </p>
        </div>
        <div className="flex gap-2.5">
          <a href="/admin/feedback" className="no-underline text-foreground font-extrabold text-[13px] hover:text-primary">
            {getText(locale, "sessions.feedbackLink")} &rarr;
          </a>
          <a href="/admin/status" className="no-underline text-foreground font-extrabold text-[13px] hover:text-primary">
            {getText(locale, "sessions.statusLink")}
          </a>
          <a href="/admin/analytics" className="no-underline text-foreground font-extrabold text-[13px] hover:text-primary">
            {getText(locale, "sessions.analyticsLink")} &rarr;
          </a>
          <a href="/admin/tuning-report" className="no-underline text-foreground font-extrabold text-[13px] hover:text-primary">
            {getText(locale, "sessions.tuningLink")} &rarr;
          </a>
          <a href="/api/admin/export/sessions" download className="no-underline text-primary font-bold text-[13px] hover:underline">
            {getText(locale, "sessions.exportCsvLink")}
          </a>
        </div>
      </div>

      <div className="flex gap-2.5 mt-4">
        <a
          href="/admin/sessions"
          className={cn(
            "py-2 px-4 rounded-[10px] border border-border no-underline text-[13px] font-bold",
            !feedbackFilter ? "bg-primary text-primary-foreground" : "bg-card text-foreground"
          )}
        >
          {getText(locale, "sessions.all")}
        </a>
        <a
          href="/admin/sessions?feedback=down"
          className={cn(
            "py-2 px-4 rounded-[10px] border border-border no-underline text-[13px] font-extrabold",
            feedbackFilter === "down" ? "bg-red-600 text-white" : "bg-card text-red-700"
          )}
        >
          {getText(locale, "sessions.downOnly")}
        </a>
        <a
          href="/admin/sessions?feedback=up"
          className={cn(
            "py-2 px-4 rounded-[10px] border border-border no-underline text-[13px] font-bold",
            feedbackFilter === "up" ? "bg-green-700 text-white" : "bg-card text-green-800"
          )}
        >
          {getText(locale, "sessions.upOnly")}
        </a>
      </div>

      <div className="mt-4 w-full overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left border-b-2 border-border bg-accent">
              <th className="p-3.5 text-[13px]">
                <a href={sessionsTableHref(params, "created_at")} className="text-primary no-underline font-semibold hover:underline">
                  {getText(locale, "sessions.time")} {sort === "created_at" && (ascending ? "↑" : "↓")}
                </a>
              </th>
              <th className="p-3.5 text-[13px]">
                <a href={sessionsTableHref(params, "envelope_type")} className="text-primary no-underline font-semibold hover:underline">
                  {getText(locale, "sessions.type")} {sort === "envelope_type" && (ascending ? "↑" : "↓")}
                </a>
              </th>
              <th className="p-3.5 text-[13px]">
                <a href={sessionsTableHref(params, "recommended_specialty_tr")} className="text-primary no-underline font-semibold hover:underline">
                  {getText(locale, "sessions.specialty")} {sort === "recommended_specialty_tr" && (ascending ? "↑" : "↓")}
                </a>
              </th>
              <th className="p-3.5 text-[13px]">
                <a href={sessionsTableHref(params, "confidence_label_tr")} className="text-primary no-underline font-semibold hover:underline">
                  {getText(locale, "sessions.confidence")} {sort === "confidence_label_tr" && (ascending ? "↑" : "↓")}
                </a>
              </th>
              <th className="p-3.5 text-[13px]">
                <a href={sessionsTableHref(params, "stop_reason")} className="text-primary no-underline font-semibold hover:underline">
                  {getText(locale, "sessions.stopReason")} {sort === "stop_reason" && (ascending ? "↑" : "↓")}
                </a>
              </th>
              <th className="p-3.5 text-[13px] text-muted-foreground"></th>
            </tr>
          </thead>
          <tbody>
            {data?.map((s) => (
              <tr key={s.id} className="border-b border-border">
                <td className="p-3.5 text-sm">{new Date(s.created_at).toLocaleString("tr-TR")}</td>
                <td className="p-3.5 text-sm">
                  <span
                    className={cn(
                      "inline-block py-0.5 px-2.5 rounded-md text-xs font-semibold",
                      s.envelope_type === "EMERGENCY" && "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300",
                      s.envelope_type === "RESULT" && "bg-green-50 text-green-800 dark:bg-green-950/50 dark:text-green-300",
                      s.envelope_type !== "EMERGENCY" && s.envelope_type !== "RESULT" && "bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
                    )}
                  >
                    {s.envelope_type}
                  </span>
                </td>
                <td className="p-3.5 text-sm">{s.recommended_specialty_tr ?? "-"}</td>
                <td className="p-3.5 text-sm">
                  {s.confidence_label_tr ?? "-"}{" "}
                  {typeof s.confidence_0_1 === "number" ? `(${Math.round(s.confidence_0_1 * 100)}%)` : ""}
                </td>
                <td className="p-3.5 text-sm text-muted-foreground">{s.stop_reason ?? "-"}</td>
                <td className="p-3.5">
                  <a href={`/admin/sessions/${s.id}`} className="text-primary font-semibold no-underline text-[13px] hover:underline">
                    {getText(locale, "sessions.view")} &rarr;
                  </a>
                </td>
              </tr>
            ))}
            {(!data || data.length === 0) && (
              <tr>
                <td colSpan={6} className="p-10 text-center text-muted-foreground">
                  {getText(locale, "sessions.noSessions")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
