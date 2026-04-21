import { cookies } from "next/headers";
import Link from "next/link";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { AckButton } from "./AckButton";

export const dynamic = "force-dynamic";

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

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border rounded-2xl p-5 bg-card text-foreground">
      <div className="text-[13px] text-muted-foreground mb-3 font-semibold uppercase tracking-wide">{title}</div>
      {children}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  accentClass,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accentClass?: string;
}) {
  return (
    <div className="p-5 rounded-xl border border-border bg-card text-foreground relative overflow-hidden">
      {accentClass && (
        <div className={cn("absolute top-0 left-0 right-0 h-0.5 rounded-t-xl", accentClass)} />
      )}
      <div className="text-xs text-muted-foreground font-medium">{label}</div>
      <div className="text-3xl font-extrabold mt-1.5 tracking-tight">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function RatingBadge({ rating, upLabel, downLabel }: { rating: string; upLabel: string; downLabel: string }) {
  const isUp = rating === "up";
  return (
    <span className={cn("inline-flex items-center gap-1 py-0.5 px-2.5 rounded-lg text-xs font-bold", isUp ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300" : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300")}>
      {isUp ? upLabel : downLabel}
    </span>
  );
}

function FilterTab({
  href,
  active,
  label,
  activeClass = "bg-primary text-primary-foreground border-primary",
  inactiveClass,
}: {
  href: string;
  active: boolean;
  label: string;
  activeClass?: string;
  inactiveClass?: string;
}) {
  return (
    <a
      href={href}
      className={cn(
        "py-2 px-4 rounded-lg border border-border no-underline font-bold text-[13px] transition-all duration-150",
        active ? activeClass : "bg-card text-foreground",
        !active && inactiveClass
      )}
    >
      {label}
    </a>
  );
}

export default async function FeedbackPage({
  searchParams,
}: {
  searchParams: Promise<{ rating?: string }>;
}) {
  await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);
  const params = await searchParams;
  const ratingFilter = params.rating;
  const sb = supabaseAdmin();

  const { count: totalFeedback } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true });

  const { count: upCount } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .eq("rating", "up");

  const { count: downCount } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .eq("rating", "down");

  const total = totalFeedback ?? 0;
  const up = upCount ?? 0;
  const down = downCount ?? 0;
  const satisfaction = total > 0 ? Math.round((up / total) * 100) : 0;

  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const { data: trendRaw } = await sb
    .from("triage_feedback")
    .select("rating,created_at")
    .gte("created_at", sevenDaysAgo.toISOString())
    .order("created_at", { ascending: true });

  const dailyMap: Record<string, { up: number; down: number }> = {};
  ((trendRaw ?? []) as Array<{ created_at: string; rating: "up" | "down" }>).forEach((r) => {
    const day = new Date(r.created_at).toISOString().slice(0, 10);
    if (!dailyMap[day]) dailyMap[day] = { up: 0, down: 0 };
    dailyMap[day][r.rating] += 1;
  });
  const trend = Object.entries(dailyMap)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([day, v]) => ({ day, ...v, total: v.up + v.down }));

  let fbQuery = sb
    .from("triage_feedback")
    .select(
      "id,session_id,rating,comment,user_selected_specialty_id,created_at,acknowledged_at,acknowledged_by,ack_note",
    )
    .order("created_at", { ascending: false })
    .limit(50);

  if (ratingFilter === "up" || ratingFilter === "down") {
    fbQuery = fbQuery.eq("rating", ratingFilter);
  }

  const { data: feedbackRows } = await fbQuery;
  const fbList = feedbackRows ?? [];

  // Typed session-detail lookup. Keeping fields optional mirrors
  // the Supabase row shape (nullable columns) without forcing us
  // to case-split on every access site; undefined on a missing
  // key degrades gracefully to an em-dash in the JSX below.
  type FeedbackSession = {
    id: string;
    envelope_type?: string | null;
    recommended_specialty_tr?: string | null;
    confidence_0_1?: number | null;
  };
  const sessionIds = [
    ...new Set(
      (fbList as Array<{ session_id: string | null }>)
        .map((r) => r.session_id)
        .filter((id): id is string => Boolean(id)),
    ),
  ];
  const sessMap: Record<string, FeedbackSession> = {};

  if (sessionIds.length > 0) {
    const { data: sessions } = await sb
      .from("triage_sessions")
      .select("id,envelope_type,recommended_specialty_tr,confidence_0_1")
      .in("id", sessionIds.slice(0, 200));

    ((sessions ?? []) as FeedbackSession[]).forEach((s) => {
      sessMap[s.id] = s;
    });
  }

  const { data: downFb } = await sb
    .from("triage_feedback")
    .select("session_id")
    .eq("rating", "down")
    .order("created_at", { ascending: false })
    .limit(500);

  const downSessionIds = [
    ...new Set(
      ((downFb ?? []) as Array<{ session_id: string | null }>)
        .map((r) => r.session_id)
        .filter((id): id is string => Boolean(id)),
    ),
  ];
  const specDownCounts: Record<string, number> = {};

  if (downSessionIds.length > 0) {
    const { data: downSessions } = await sb
      .from("triage_sessions")
      .select("id,recommended_specialty_tr")
      .in("id", downSessionIds.slice(0, 200));

    const dMap: Record<string, string> = {};
    ((downSessions ?? []) as Array<{ id: string; recommended_specialty_tr?: string | null }>).forEach((s) => {
      dMap[s.id] = s.recommended_specialty_tr ?? getText(locale, "analytics.unknown");
    });

    downSessionIds.forEach((sid) => {
      const spec = dMap[sid] ?? getText(locale, "analytics.unknown");
      specDownCounts[spec] = (specDownCounts[spec] || 0) + 1;
    });
  }

  const topDownSpecs = Object.entries(specDownCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  const maxBar = Math.max(...trend.map((item) => item.total), 1);
  const maxDownSpec = Math.max(...topDownSpecs.map(([, c]) => c), 1);

  const positiveRate = `${total > 0 ? Math.round((up / total) * 100) : 0}% ${t("feedback.rateSuffix")}`;
  const negativeRate = `${total > 0 ? Math.round((down / total) * 100) : 0}% ${t("feedback.rateSuffix")}`;

  const satisfactionLabel =
    satisfaction >= 80
      ? t("feedback.satisfactionGreat")
      : satisfaction >= 50
        ? t("feedback.satisfactionGood")
        : t("feedback.satisfactionNeeds");

  return (
    <div className="p-6 max-w-[1200px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: t("feedback.title") }]} />
      <div className="flex justify-between items-center flex-wrap gap-3">
        <div>
          <h1 className="text-[26px] font-black m-0">{t("feedback.title")}</h1>
          <p className="text-muted-foreground mt-1.5 text-[13px]">{t("feedback.subtitle")}</p>
        </div>
        <div className="flex gap-3">
          <Link href="/admin/sessions" className="font-bold text-primary no-underline text-[13px]">
            {t("feedback.sessionsLink")} &rarr;
          </Link>
          <a href="/admin/analytics" className="font-bold text-primary no-underline text-[13px]">
            {t("feedback.analyticsLink")} &rarr;
          </a>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3.5 mt-6">
        <StatCard label={t("feedback.totalFeedback")} value={total} accentClass="bg-gradient-to-r from-indigo-500 to-violet-500" />
        <StatCard label={t("feedback.positive")} value={up} sub={positiveRate} accentClass="bg-green-800" />
        <StatCard label={t("feedback.negative")} value={down} sub={negativeRate} accentClass="bg-red-800" />
        <StatCard
          label={t("feedback.satisfaction")}
          value={`%${satisfaction}`}
          sub={satisfactionLabel}
          accentClass={satisfaction >= 80 ? "bg-green-800" : satisfaction >= 50 ? "bg-amber-600" : "bg-red-800"}
        />
      </div>

      <div className="grid grid-cols-[2fr_1fr] gap-4 mt-5">
        <Card title={t("feedback.trendTitle")}>
          {trend.length === 0 ? (
            <div className="text-muted-foreground text-[13px]">{t("feedback.noTrend")}</div>
          ) : (
            <div className="flex flex-col gap-2">
              {trend.map((item) => (
                <div key={item.day} className="flex items-center gap-2.5">
                  <span className="text-xs text-muted-foreground min-w-[80px] font-medium">{item.day.slice(5)}</span>
                  <div className="flex-1 flex gap-0.5 h-[22px]">
                    <div
                      className="bg-gradient-to-r from-green-600 to-green-500 rounded-l min-w-0 transition-[width] duration-300"
                      style={{ width: `${(item.up / maxBar) * 100}%`, minWidth: item.up > 0 ? 4 : 0 }}
                    />
                    <div
                      className="bg-gradient-to-r from-red-600 to-red-400 rounded-r min-w-0 transition-[width] duration-300"
                      style={{ width: `${(item.down / maxBar) * 100}%`, minWidth: item.down > 0 ? 4 : 0 }}
                    />
                  </div>
                  <span className="text-[11px] text-muted-foreground min-w-[60px]">
                    <span className="text-green-600 dark:text-green-400">{item.up}^</span>{" "}
                    <span className="text-red-600 dark:text-red-400">{item.down}v</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title={t("feedback.topDownTitle")}>
          {topDownSpecs.length === 0 ? (
            <div className="text-muted-foreground text-[13px]">{t("feedback.noNegative")}</div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {topDownSpecs.map(([spec, cnt], i) => (
                <div key={i}>
                  <div className="flex justify-between items-center mb-0.5">
                    <span className="text-[13px] font-medium">{spec}</span>
                    <span className="text-xs font-bold text-red-800 dark:text-red-400">{cnt}</span>
                  </div>
                  <div className="h-1.5 rounded-sm bg-border overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-red-600 to-red-400 rounded-sm transition-[width] duration-300"
                      style={{ width: `${(cnt / maxDownSpec) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="flex gap-2.5 mt-7 items-center">
        <span className="text-[15px] font-extrabold">{t("feedback.recentTitle")}</span>
        <div className="flex gap-2 ml-auto">
          <FilterTab href="/admin/feedback" active={!ratingFilter} label={t("feedback.all")} />
          <FilterTab href="/admin/feedback?rating=up" active={ratingFilter === "up"} label={t("feedback.up")} activeClass="bg-green-800 text-white border-green-800" />
          <FilterTab href="/admin/feedback?rating=down" active={ratingFilter === "down"} label={t("feedback.down")} activeClass="bg-red-800 text-white border-red-800" />
        </div>
      </div>

      <div className="w-full mt-3 rounded-xl overflow-hidden border border-border bg-card shadow-sm">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left border-b-2 border-border bg-accent">
              <th className="p-3.5 text-xs font-semibold text-muted-foreground">{t("feedback.date")}</th>
              <th className="p-3.5 text-xs font-semibold text-muted-foreground">{t("feedback.rating")}</th>
              <th className="p-3.5 text-xs font-semibold text-muted-foreground">{t("feedback.specialty")}</th>
              <th className="p-3.5 text-xs font-semibold text-muted-foreground">{t("feedback.confidence")}</th>
              <th className="p-3.5 text-xs font-semibold text-muted-foreground">{t("feedback.comment")}</th>
              <th className="p-3.5 text-xs font-semibold text-muted-foreground" />
            </tr>
          </thead>
          <tbody>
            {(fbList as Array<{
              id: string;
              session_id: string;
              rating: string;
              comment?: string | null;
              user_selected_specialty_id?: string | null;
              created_at: string;
              acknowledged_at?: string | null;
              acknowledged_by?: string | null;
              ack_note?: string | null;
            }>).map((row) => {
              const sess = sessMap[row.session_id] || ({} as FeedbackSession);
              return (
                <tr key={row.id} className="border-b border-border transition-colors hover:bg-muted/20">
                  <td className="p-3.5 text-[13px]">
                    {new Date(row.created_at).toLocaleString(locale === "en" ? "en-US" : "tr-TR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="p-3.5">
                    <RatingBadge rating={row.rating} upLabel={t("feedback.up")} downLabel={t("feedback.down")} />
                  </td>
                  <td className="p-3.5 text-[13px]">
                    {sess.recommended_specialty_tr ?? <span className="text-muted-foreground">-</span>}
                  </td>
                  <td className="p-3.5 text-[13px]">
                    {typeof sess.confidence_0_1 === "number" ? (
                      <span
                        className={cn(
                          "font-semibold",
                          sess.confidence_0_1 >= 0.75 && "text-green-800 dark:text-green-400",
                          sess.confidence_0_1 >= 0.5 && sess.confidence_0_1 < 0.75 && "text-amber-600 dark:text-amber-400",
                          sess.confidence_0_1 < 0.5 && "text-red-800 dark:text-red-400"
                        )}
                      >
                        {Math.round(sess.confidence_0_1 * 100)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </td>
                  <td
                    className={cn("p-3.5 text-[13px] max-w-[260px] overflow-hidden text-ellipsis whitespace-nowrap", row.comment ? "text-foreground" : "text-muted-foreground")}
                    title={row.comment || undefined}
                  >
                    {row.comment || "-"}
                  </td>
                  <td className="p-3.5">
                    <div className="flex flex-col items-start gap-1.5">
                      <a href={`/admin/sessions/${row.session_id}`} className="text-primary font-semibold no-underline text-xs">
                        {t("feedback.detail")} &rarr;
                      </a>
                      <AckButton
                        feedbackId={row.id}
                        acknowledgedAt={row.acknowledged_at ?? null}
                        acknowledgedBy={row.acknowledged_by ?? null}
                        ackNote={row.ack_note ?? null}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
            {fbList.length === 0 && (
              <tr>
                <td colSpan={6} className="p-10 text-center text-muted-foreground text-sm">
                  {ratingFilter ? formatText(t("feedback.noFeedbackForFilter"), { rating: ratingFilter }) : t("feedback.noFeedback")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
