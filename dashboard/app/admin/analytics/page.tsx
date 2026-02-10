import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";

export const dynamic = "force-dynamic";

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        border: "1px solid #eee",
        borderRadius: 16,
        padding: 20,
        background: "white",
      }}
    >
      <div
        style={{
          fontSize: 13,
          color: "#666",
          marginBottom: 12,
          fontWeight: 600,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div
      style={{
        padding: 18,
        borderRadius: 14,
        border: "1px solid #eee",
        backgroundColor: "#fff",
      }}
    >
      <div style={{ fontSize: 12, color: "#666" }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, marginTop: 4 }}>{value}</div>
      {sub && (
        <div style={{ fontSize: 12, color: "#999", marginTop: 2 }}>{sub}</div>
      )}
    </div>
  );
}

export default async function AnalyticsPage() {
  await requireAdmin();
  const sb = supabaseAdmin();

  // Total sessions
  const { count: totalSessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true });

  // Total RESULT sessions
  const { count: resultSessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "RESULT");

  // Total EMERGENCY sessions
  const { count: emergencySessions } = await sb
    .from("triage_sessions")
    .select("id", { count: "exact", head: true })
    .eq("envelope_type", "EMERGENCY");

  // Feedback counts
  const { data: fbUp } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .eq("rating", "up");
  const { data: fbDown } = await sb
    .from("triage_feedback")
    .select("id", { count: "exact", head: true })
    .eq("rating", "down");

  // Specialty distribution (top 10)
  const { data: specDist } = await sb
    .from("triage_sessions")
    .select("recommended_specialty_tr")
    .eq("envelope_type", "RESULT")
    .not("recommended_specialty_tr", "is", null)
    .order("created_at", { ascending: false })
    .limit(500);

  const specCounts: Record<string, number> = {};
  (specDist ?? []).forEach((s: any) => {
    const k = s.recommended_specialty_tr || "Unknown";
    specCounts[k] = (specCounts[k] || 0) + 1;
  });
  const specRanked = Object.entries(specCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  // Confidence distribution
  const { data: confDist } = await sb
    .from("triage_sessions")
    .select("confidence_label_tr")
    .eq("envelope_type", "RESULT")
    .not("confidence_label_tr", "is", null)
    .limit(500);

  const confCounts: Record<string, number> = {};
  (confDist ?? []).forEach((s: any) => {
    const k = s.confidence_label_tr || "Unknown";
    confCounts[k] = (confCounts[k] || 0) + 1;
  });

  // Confusion matrix: down feedback with user_selected_specialty
  const { data: confusionRaw } = await sb
    .from("triage_feedback")
    .select("session_id,rating,user_selected_specialty_id")
    .eq("rating", "down")
    .not("user_selected_specialty_id", "is", null)
    .order("created_at", { ascending: false })
    .limit(200);

  // For confusion matrix, we need session specialty too
  const confusionSessionIds = (confusionRaw ?? []).map((f: any) => f.session_id);
  let confusionRows: { predicted: string; actual: string; cnt: number }[] = [];

  if (confusionSessionIds.length > 0) {
    const { data: confSessions } = await sb
      .from("triage_sessions")
      .select("id,recommended_specialty_tr")
      .in("id", confusionSessionIds.slice(0, 100));

    const sessionSpec: Record<string, string> = {};
    (confSessions ?? []).forEach((s: any) => {
      sessionSpec[s.id] = s.recommended_specialty_tr ?? "Unknown";
    });

    const confPairs: Record<string, number> = {};
    (confusionRaw ?? []).forEach((f: any) => {
      const predicted = sessionSpec[f.session_id] ?? "Unknown";
      const actual = f.user_selected_specialty_id ?? "Unknown";
      const key = `${predicted}|||${actual}`;
      confPairs[key] = (confPairs[key] || 0) + 1;
    });

    confusionRows = Object.entries(confPairs)
      .map(([key, cnt]) => {
        const [predicted, actual] = key.split("|||");
        return { predicted, actual, cnt };
      })
      .sort((a, b) => b.cnt - a.cnt);
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Analytics</h1>
        <div style={{ display: "flex", gap: 12 }}>
          <a
            href="/admin/sessions"
            style={{ fontWeight: 700, color: "#111", textDecoration: "none", fontSize: 13 }}
          >
            Sessions &rarr;
          </a>
          <a
            href="/admin/tuning-report"
            style={{ fontWeight: 700, color: "#111", textDecoration: "none", fontSize: 13 }}
          >
            Tuning &rarr;
          </a>
        </div>
      </div>

      {/* Top stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 12,
          marginTop: 20,
        }}
      >
        <Stat label="Total Sessions" value={totalSessions ?? 0} />
        <Stat label="RESULT" value={resultSessions ?? 0} />
        <Stat label="EMERGENCY" value={emergencySessions ?? 0} />
        <Stat
          label="Feedback"
          value={`${(fbUp as any)?.length ?? 0} / ${(fbDown as any)?.length ?? 0}`}
          sub="up / down"
        />
      </div>

      {/* Specialty distribution + Confidence */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginTop: 20,
        }}
      >
        <Card title="Specialty Distribution (last 500 RESULT)">
          {specRanked.map(([name, cnt], i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 0",
                borderBottom: "1px solid #f5f5f5",
              }}
            >
              <span style={{ fontSize: 14 }}>{name}</span>
              <span style={{ fontWeight: 700, fontSize: 14 }}>{cnt}</span>
            </div>
          ))}
        </Card>

        <Card title="Confidence Distribution">
          {Object.entries(confCounts).map(([label, cnt], i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 0",
                borderBottom: "1px solid #f5f5f5",
              }}
            >
              <span
                style={{
                  fontSize: 14,
                  color:
                    label === "Yüksek"
                      ? "#2E7D32"
                      : label === "Orta"
                        ? "#F57F17"
                        : "#C62828",
                  fontWeight: 600,
                }}
              >
                {label}
              </span>
              <span style={{ fontWeight: 700, fontSize: 14 }}>{cnt}</span>
            </div>
          ))}
        </Card>
      </div>

      {/* Confusion Matrix */}
      <div style={{ marginTop: 20 }}>
        <Card title="Specialty Confusion Matrix (down feedback with user_selected_specialty)">
          {confusionRows.length === 0 ? (
            <div style={{ color: "#999", fontSize: 13 }}>
              No confusion data yet. Users need to provide
              user_selected_specialty_id in down feedback.
            </div>
          ) : (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 13,
              }}
            >
              <thead>
                <tr style={{ borderBottom: "2px solid #eee", textAlign: "left" }}>
                  <th style={{ padding: 10 }}>Predicted</th>
                  <th style={{ padding: 10 }}>Actual (user)</th>
                  <th style={{ padding: 10 }}>Count</th>
                </tr>
              </thead>
              <tbody>
                {confusionRows.map((r, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                    <td style={{ padding: 10 }}>{r.predicted}</td>
                    <td style={{ padding: 10, fontWeight: 600 }}>{r.actual}</td>
                    <td style={{ padding: 10, fontWeight: 700 }}>{r.cnt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
