import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import {
  listReports,
  getSignedReportUrl,
  fetchJsonFromSignedUrl,
} from "@/lib/reports";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

function Pre({ obj }: { obj: unknown }) {
  return (
    <pre className="bg-zinc-900 text-zinc-200 p-4 rounded-xl overflow-x-auto text-xs leading-normal">
      {JSON.stringify(obj, null, 2)}
    </pre>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border rounded-2xl p-[18px] bg-card text-foreground">
      <div className="text-xs text-muted-foreground mb-2.5 font-semibold">{title}</div>
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
  const locale = await getLocale();
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
    <div className="p-6 max-w-[1400px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.tuningReport") }]} />
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-[26px] font-black m-0">{getText(locale, "tuningReport.title")}</h1>
          <div className="text-muted-foreground mt-1.5 text-[13px]">
            {report
              ? getText(locale, "tuningReport.generated").replace("{generated}", report.generated_at ?? "").replace("{days}", String(report.window_days ?? 0))
              : getText(locale, "tuningReport.noReportSelected")}
          </div>
        </div>
        <div className="flex gap-3">
          <a href="/admin/analytics" className="font-bold text-primary no-underline text-[13px]">
            {getText(locale, "tuningReport.analyticsLink")}
          </a>
          <a href="/admin/sessions" className="font-bold text-primary no-underline text-[13px]">
            {getText(locale, "tuningReport.sessionsLink")}
          </a>
        </div>
      </div>

      <div className="grid grid-cols-[280px_1fr] gap-4 mt-5">
        <Card title={getText(locale, "tuningReport.reports")}>
          <div className="flex flex-col gap-2 max-h-[600px] overflow-y-auto">
            {files.length === 0 && (
              <div className="text-muted-foreground text-[13px]">{getText(locale, "tuningReport.noReportsInStorage")}</div>
            )}
            {files.map((f) => (
              <a
                key={f.name}
                href={`/admin/tuning-report?file=${encodeURIComponent(f.name)}`}
                className={cn(
                  "no-underline p-2.5 rounded-lg border border-border font-bold text-xs",
                  f.name === selected ? "bg-primary text-primary-foreground border-primary" : "bg-background text-foreground"
                )}
              >
                {f.name}
              </a>
            ))}
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          {!report ? (
            <Card title={getText(locale, "tuningReport.noReport")}>
              <div className="text-muted-foreground">{getText(locale, "tuningReport.selectReportOrRun")}</div>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Card title={getText(locale, "tuningReport.feedbackCounts")}>
                  <Pre obj={report.feedback_counts ?? []} />
                </Card>
                <Card title={getText(locale, "tuningReport.specialtyDownRate")}>
                  <Pre obj={report.specialty_down_rate ?? []} />
                </Card>
              </div>

              {Array.isArray(report.synonym_suggestions) && report.synonym_suggestions.length > 0 && (
                <Card title={getText(locale, "tuningReport.synonymSuggestions")}>
                  <table className="w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="p-2">{getText(locale, "tuningReport.token")}</th>
                        <th className="p-2">{getText(locale, "tuningReport.suggestedCanonical")}</th>
                        <th className="p-2">{getText(locale, "tuningReport.count")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.synonym_suggestions.slice(0, 30).map((s: any, i: number) => (
                        <tr key={i} className="border-b border-border">
                          <td className="p-2 font-semibold">{s.token}</td>
                          <td className="p-2 text-muted-foreground">{s.suggested_canonical ?? "-"}</td>
                          <td className="p-2">{s.support_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>
              )}

              {Array.isArray(report.question_effectiveness_top) && report.question_effectiveness_top.length > 0 && (
                <Card title={getText(locale, "tuningReport.questionEffectivenessTop")}>
                  <Pre obj={report.question_effectiveness_top} />
                </Card>
              )}

              <Card title={getText(locale, "tuningReport.downExamples")}>
                <Pre obj={report.down_examples ?? []} />
              </Card>

              <div className="grid grid-cols-2 gap-3">
                <Card title={getText(locale, "tuningReport.stopReasonBreakdown")}>
                  <Pre obj={report.stop_reason_breakdown ?? []} />
                </Card>
                <Card title={getText(locale, "tuningReport.mostAskedCanonicals")}>
                  <Pre obj={report.most_asked_canonicals ?? []} />
                </Card>
              </div>

              <Card title={getText(locale, "tuningReport.confidenceDistribution")}>
                <Pre obj={report.confidence_distribution ?? []} />
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
