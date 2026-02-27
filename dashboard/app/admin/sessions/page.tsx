import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseServerAuthed } from "@/lib/supabaseServerAuthed";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";

export const dynamic = "force-dynamic";

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
  const params = await searchParams;
  const { feedback: feedbackFilter, sort: sortCol, order: orderDir } = params;
  const sort: (typeof SORT_COLUMNS)[number] = SORT_COLUMNS.includes(sortCol as (typeof SORT_COLUMNS)[number])
    ? (sortCol as (typeof SORT_COLUMNS)[number])
    : "created_at";
  const ascending = orderDir === "asc";

  // Use admin client for data fetching (RLS bypass, works without auth setup)
  const sb = supabaseAdmin();

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

  if (error) return <div style={{ padding: 24 }}>Error: {error.message}</div>;

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto", background: "var(--dash-bg)", color: "var(--dash-text)" }}>
      <Breadcrumb items={[{ label: "Admin", href: "/admin/sessions" }, { label: "Sessions" }]} />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Sessions</h1>
          <p style={{ color: "var(--dash-text-muted)", marginTop: 6 }}>
            Last 100 triage sessions
            {feedbackFilter ? ` \u2022 Filter: feedback=${feedbackFilter}` : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <a
            href="/admin/status"
            style={{ textDecoration: "none", color: "var(--dash-text)", fontWeight: 800, fontSize: 13 }}
          >
            Sistem durumu
          </a>
          <a
            href="/admin/analytics"
            style={{ textDecoration: "none", color: "var(--dash-text)", fontWeight: 800, fontSize: 13 }}
          >
            Analytics &rarr;
          </a>
          <a
            href="/admin/tuning-report"
            style={{ textDecoration: "none", color: "var(--dash-text)", fontWeight: 800, fontSize: 13 }}
          >
            Tuning &rarr;
          </a>
          <a
            href="/api/admin/export/sessions"
            download
            style={{ textDecoration: "none", color: "var(--dash-accent)", fontWeight: 700, fontSize: 13 }}
          >
            Export CSV
          </a>
        </div>
      </div>

      {/* Feedback filter tabs */}
      <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
        <a
          href="/admin/sessions"
          style={{
            padding: "8px 16px",
            borderRadius: 10,
            border: "1px solid var(--dash-border)",
            textDecoration: "none",
            color: !feedbackFilter ? "var(--dash-bg)" : "var(--dash-text)",
            backgroundColor: !feedbackFilter ? "var(--dash-accent)" : "var(--dash-bg-card)",
            fontWeight: 700,
            fontSize: 13,
          }}
        >
          All
        </a>
        <a
          href="/admin/sessions?feedback=down"
          style={{
            padding: "8px 16px",
            borderRadius: 10,
            border: "1px solid var(--dash-border)",
            textDecoration: "none",
            color: feedbackFilter === "down" ? "#fff" : "#b00020",
            backgroundColor: feedbackFilter === "down" ? "#b00020" : "var(--dash-bg-card)",
            fontWeight: 800,
            fontSize: 13,
          }}
        >
          Down only
        </a>
        <a
          href="/admin/sessions?feedback=up"
          style={{
            padding: "8px 16px",
            borderRadius: 10,
            border: "1px solid var(--dash-border)",
            textDecoration: "none",
            color: feedbackFilter === "up" ? "#fff" : "#2E7D32",
            backgroundColor: feedbackFilter === "up" ? "#2E7D32" : "var(--dash-bg-card)",
            fontWeight: 700,
            fontSize: 13,
          }}
        >
          Up only
        </a>
      </div>

      <table
        style={{
          width: "100%",
          marginTop: 16,
          borderCollapse: "collapse",
          backgroundColor: "var(--dash-bg-card)",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
          border: "1px solid var(--dash-border)",
        }}
      >
        <thead>
          <tr
            style={{
              textAlign: "left",
              borderBottom: "2px solid var(--dash-border)",
              backgroundColor: "var(--dash-accent-bg)",
            }}
          >
            <th style={{ padding: 14, fontSize: 13 }}>
              <a href={sessionsTableHref(params, "created_at")} style={{ color: "var(--dash-accent)", textDecoration: "none", fontWeight: 600 }}>
                Time {sort === "created_at" && (ascending ? "↑" : "↓")}
              </a>
            </th>
            <th style={{ padding: 14, fontSize: 13 }}>
              <a href={sessionsTableHref(params, "envelope_type")} style={{ color: "var(--dash-accent)", textDecoration: "none", fontWeight: 600 }}>
                Type {sort === "envelope_type" && (ascending ? "↑" : "↓")}
              </a>
            </th>
            <th style={{ padding: 14, fontSize: 13 }}>
              <a href={sessionsTableHref(params, "recommended_specialty_tr")} style={{ color: "var(--dash-accent)", textDecoration: "none", fontWeight: 600 }}>
                Specialty {sort === "recommended_specialty_tr" && (ascending ? "↑" : "↓")}
              </a>
            </th>
            <th style={{ padding: 14, fontSize: 13 }}>
              <a href={sessionsTableHref(params, "confidence_label_tr")} style={{ color: "var(--dash-accent)", textDecoration: "none", fontWeight: 600 }}>
                Confidence {sort === "confidence_label_tr" && (ascending ? "↑" : "↓")}
              </a>
            </th>
            <th style={{ padding: 14, fontSize: 13 }}>
              <a href={sessionsTableHref(params, "stop_reason")} style={{ color: "var(--dash-accent)", textDecoration: "none", fontWeight: 600 }}>
                Stop {sort === "stop_reason" && (ascending ? "↑" : "↓")}
              </a>
            </th>
            <th style={{ padding: 14, fontSize: 13, color: "var(--dash-text-muted)" }}></th>
          </tr>
        </thead>
        <tbody>
          {data?.map((s) => (
            <tr key={s.id} style={{ borderBottom: "1px solid var(--dash-border)" }}>
              <td style={{ padding: 14, fontSize: 14 }}>
                {new Date(s.created_at).toLocaleString("tr-TR")}
              </td>
              <td style={{ padding: 14, fontSize: 14 }}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "2px 10px",
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    backgroundColor:
                      s.envelope_type === "EMERGENCY"
                        ? "#FFEBEE"
                        : s.envelope_type === "RESULT"
                          ? "#E8F5E9"
                          : "#FFF8E1",
                    color:
                      s.envelope_type === "EMERGENCY"
                        ? "#C62828"
                        : s.envelope_type === "RESULT"
                          ? "#2E7D32"
                          : "#F57F17",
                  }}
                >
                  {s.envelope_type}
                </span>
              </td>
              <td style={{ padding: 14, fontSize: 14 }}>
                {s.recommended_specialty_tr ?? "-"}
              </td>
              <td style={{ padding: 14, fontSize: 14 }}>
                {s.confidence_label_tr ?? "-"}{" "}
                {typeof s.confidence_0_1 === "number"
                  ? `(${Math.round(s.confidence_0_1 * 100)}%)`
                  : ""}
              </td>
              <td style={{ padding: 14, fontSize: 14, color: "var(--dash-text-muted)" }}>
                {s.stop_reason ?? "-"}
              </td>
              <td style={{ padding: 14 }}>
                <a
                  href={`/admin/sessions/${s.id}`}
                  style={{
                    color: "var(--dash-accent)",
                    fontWeight: 600,
                    textDecoration: "none",
                    fontSize: 13,
                  }}
                >
                  View &rarr;
                </a>
              </td>
            </tr>
          ))}
          {(!data || data.length === 0) && (
            <tr>
              <td
                colSpan={6}
                style={{ padding: 40, textAlign: "center", color: "var(--dash-text-muted)" }}
              >
                No sessions found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
