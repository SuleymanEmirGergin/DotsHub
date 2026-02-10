import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseServerAuthed } from "@/lib/supabaseServerAuthed";
import { supabaseAdmin } from "@/lib/supabaseServer";

export const dynamic = "force-dynamic";

export default async function SessionsPage({
  searchParams,
}: {
  searchParams: Promise<{ feedback?: string }>;
}) {
  await requireAdmin();
  const { feedback: feedbackFilter } = await searchParams;

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
    .order("created_at", { ascending: false })
    .limit(100);

  if (sessionIds) q = q.in("id", sessionIds);

  const { data, error } = await q;

  if (error) return <div style={{ padding: 24 }}>Error: {error.message}</div>;

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Sessions</h1>
          <p style={{ color: "#666", marginTop: 6 }}>
            Last 100 triage sessions
            {feedbackFilter ? ` \u2022 Filter: feedback=${feedbackFilter}` : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <a
            href="/admin/analytics"
            style={{ textDecoration: "none", color: "#111", fontWeight: 800, fontSize: 13 }}
          >
            Analytics &rarr;
          </a>
          <a
            href="/admin/tuning-report"
            style={{ textDecoration: "none", color: "#111", fontWeight: 800, fontSize: 13 }}
          >
            Tuning &rarr;
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
            border: "1px solid #eee",
            textDecoration: "none",
            color: !feedbackFilter ? "#fff" : "#111",
            backgroundColor: !feedbackFilter ? "#111" : "#fff",
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
            border: "1px solid #eee",
            textDecoration: "none",
            color: feedbackFilter === "down" ? "#fff" : "#b00020",
            backgroundColor: feedbackFilter === "down" ? "#b00020" : "#fff",
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
            border: "1px solid #eee",
            textDecoration: "none",
            color: feedbackFilter === "up" ? "#fff" : "#2E7D32",
            backgroundColor: feedbackFilter === "up" ? "#2E7D32" : "#fff",
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
          backgroundColor: "#fff",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        }}
      >
        <thead>
          <tr
            style={{
              textAlign: "left",
              borderBottom: "2px solid #f0f0f0",
              backgroundColor: "#fafafa",
            }}
          >
            <th style={{ padding: 14, fontSize: 13, color: "#666" }}>Time</th>
            <th style={{ padding: 14, fontSize: 13, color: "#666" }}>Type</th>
            <th style={{ padding: 14, fontSize: 13, color: "#666" }}>Specialty</th>
            <th style={{ padding: 14, fontSize: 13, color: "#666" }}>Confidence</th>
            <th style={{ padding: 14, fontSize: 13, color: "#666" }}>Stop</th>
            <th style={{ padding: 14, fontSize: 13, color: "#666" }}></th>
          </tr>
        </thead>
        <tbody>
          {data?.map((s) => (
            <tr key={s.id} style={{ borderBottom: "1px solid #f3f3f3" }}>
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
              <td style={{ padding: 14, fontSize: 14, color: "#888" }}>
                {s.stop_reason ?? "-"}
              </td>
              <td style={{ padding: 14 }}>
                <a
                  href={`/admin/sessions/${s.id}`}
                  style={{
                    color: "#111",
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
                style={{ padding: 40, textAlign: "center", color: "#999" }}
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
