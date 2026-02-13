import { requireAdmin } from "@/lib/requireAdmin";
import {
  listReports,
  getSignedReportUrl,
  fetchJsonFromSignedUrl,
} from "@/lib/reports";
import { Breadcrumb } from "@/app/components/Breadcrumb";

export const dynamic = "force-dynamic";

function Pre({ obj }: { obj: unknown }) {
  return (
    <pre
      style={{
        background: "#0b0b0b",
        color: "#e0e0e0",
        padding: 16,
        borderRadius: 14,
        overflowX: "auto",
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      {JSON.stringify(obj, null, 2)}
    </pre>
  );
}

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
        border: "1px solid var(--dash-border)",
        borderRadius: 16,
        padding: 18,
        background: "var(--dash-bg-card)",
        color: "var(--dash-text)",
      }}
    >
      <div style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 10, fontWeight: 600 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

export default async function TuningReportPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string }>;
}) {
  await requireAdmin();
  const { file } = await searchParams;

  let files: any[] = [];
  try {
    files = await listReports(20);
  } catch {
    // Storage not configured yet
  }

  const selected = file ?? files?.[0]?.name;

  let report: any = null;
  if (selected) {
    try {
      const url = await getSignedReportUrl(selected);
      report = await fetchJsonFromSignedUrl(url);
    } catch {
      // File not found or storage error
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto", background: "var(--dash-bg)", color: "var(--dash-text)", minHeight: "100vh" }}>
      <Breadcrumb items={[{ label: "Admin", href: "/admin/sessions" }, { label: "Tuning report" }]} />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>
            Tuning Report
          </h1>
          <div style={{ color: "var(--dash-text-muted)", marginTop: 6, fontSize: 13 }}>
            {report
              ? `Generated: ${report.generated_at} \u2022 Window: ${report.window_days} days`
              : "No report selected"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <a
            href="/admin/analytics"
            style={{ fontWeight: 700, color: "var(--dash-accent)", textDecoration: "none", fontSize: 13 }}
          >
            Analytics &rarr;
          </a>
          <a
            href="/admin/sessions"
            style={{ fontWeight: 700, color: "var(--dash-accent)", textDecoration: "none", fontSize: 13 }}
          >
            Sessions &rarr;
          </a>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "280px 1fr",
          gap: 16,
          marginTop: 20,
        }}
      >
        {/* Sidebar: report list */}
        <Card title="Reports">
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              maxHeight: 600,
              overflowY: "auto",
            }}
          >
            {files.length === 0 && (
              <div style={{ color: "var(--dash-text-muted)", fontSize: 13 }}>
                No reports in Storage yet. Run tuning_report_upload.py.
              </div>
            )}
            {files.map((f) => (
              <a
                key={f.name}
                href={`/admin/tuning-report?file=${encodeURIComponent(f.name)}`}
                style={{
                  textDecoration: "none",
                  padding: 10,
                  borderRadius: 10,
                  border: "1px solid var(--dash-border)",
                  background: f.name === selected ? "var(--dash-accent)" : "var(--dash-bg)",
                  color: f.name === selected ? "var(--dash-bg)" : "var(--dash-text)",
                  fontWeight: 700,
                  fontSize: 12,
                }}
              >
                {f.name}
              </a>
            ))}
          </div>
        </Card>

        {/* Main content */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {!report ? (
            <Card title="No report">
              <div style={{ color: "var(--dash-text-muted)" }}>
                Select a report from the sidebar, or run the upload script.
              </div>
            </Card>
          ) : (
            <>
              {/* Top row: counts */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                <Card title="Feedback Counts">
                  <Pre obj={report.feedback_counts ?? []} />
                </Card>
                <Card title="Specialty Down Rate">
                  <Pre obj={report.specialty_down_rate ?? []} />
                </Card>
              </div>

              {/* Synonym suggestions */}
              {Array.isArray(report.synonym_suggestions) &&
                report.synonym_suggestions.length > 0 && (
                  <Card title="Synonym Suggestions (deterministic)">
                    <table
                      style={{
                        width: "100%",
                        borderCollapse: "collapse",
                        fontSize: 13,
                      }}
                    >
                      <thead>
                        <tr style={{ borderBottom: "1px solid #eee", textAlign: "left" }}>
                          <th style={{ padding: 8 }}>Token</th>
                          <th style={{ padding: 8 }}>Suggested Canonical</th>
                          <th style={{ padding: 8 }}>Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.synonym_suggestions
                          .slice(0, 30)
                          .map((s: any, i: number) => (
                            <tr
                              key={i}
                              style={{ borderBottom: "1px solid #f5f5f5" }}
                            >
                              <td style={{ padding: 8, fontWeight: 600 }}>
                                {s.token}
                              </td>
                              <td style={{ padding: 8, color: "#666" }}>
                                {s.suggested_canonical ?? "-"}
                              </td>
                              <td style={{ padding: 8 }}>{s.support_count}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </Card>
                )}

              {/* Question effectiveness (if embedded) */}
              {Array.isArray(report.question_effectiveness_top) &&
                report.question_effectiveness_top.length > 0 && (
                  <Card title="Question Effectiveness (top)">
                    <Pre obj={report.question_effectiveness_top} />
                  </Card>
                )}

              {/* Down examples */}
              <Card title="Down Feedback Examples (top)">
                <Pre obj={report.down_examples ?? []} />
              </Card>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 12,
                }}
              >
                <Card title="Stop Reason Breakdown">
                  <Pre obj={report.stop_reason_breakdown ?? []} />
                </Card>
                <Card title="Most Asked Canonicals">
                  <Pre obj={report.most_asked_canonicals ?? []} />
                </Card>
              </div>

              {/* Confidence distribution */}
              <Card title="Confidence Distribution">
                <Pre obj={report.confidence_distribution ?? []} />
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
