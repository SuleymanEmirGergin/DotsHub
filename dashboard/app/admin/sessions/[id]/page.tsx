import { cookies } from "next/headers";
import Link from "next/link";
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

function Pretty({ data }: { data: unknown }) {
  return (
    <pre className="bg-accent p-4 rounded-xl overflow-x-auto text-[13px] leading-snug border border-border text-foreground">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function Bullets({ arr }: { arr: unknown }) {
  if (!Array.isArray(arr) || arr.length === 0) {
    return <div className="text-muted-foreground p-2">-</div>;
  }
  return (
    <ul className="mt-2 pl-[18px] mb-0">
      {arr.map((x: unknown, i: number) => (
        <li key={i} className="mb-1.5 leading-normal">{String(x)}</li>
      ))}
    </ul>
  );
}

// Type-narrowed top_conditions entry. Matches ResultPayload.top_conditions
// in the mobile client and the envelope shape in triage_engine.py.
// Every field except disease_label is optional — pre-C2 sessions and
// Kaggle candidates will be missing most of these.
type TopConditionRow = {
  disease_label?: string;
  score_0_1?: number;
  source_type?: "curated" | "kaggle_candidate";
  icd10?: string;
  disease_description?: string;
  disease_description_tr?: string;
  doktora_sorulacak_sorular_tr?: string[];
  izlenecek_belirtiler_tr?: string[];
  ne_zaman_tekrar_basvur_tr?: string[];
  self_care_tr?: string[];
  aciliyet_notu_tr?: string;
  ipucu_tr?: string;
  disclaimer_tr?: string;
};

function TopConditionsPanel({ conditions }: { conditions: unknown }) {
  if (!Array.isArray(conditions) || conditions.length === 0) {
    return <div className="text-muted-foreground p-2">-</div>;
  }
  const rows = conditions as TopConditionRow[];
  const disclaimer = rows.find((c) => c?.disclaimer_tr)?.disclaimer_tr;
  return (
    <div className="space-y-3">
      {rows.map((c, i) => {
        const curated = c.source_type === "curated";
        const pct = typeof c.score_0_1 === "number" ? Math.round(c.score_0_1 * 100) : null;
        const description = c.disease_description_tr ?? c.disease_description;
        const hasPrep =
          !!description ||
          !!c.icd10 ||
          (c.doktora_sorulacak_sorular_tr?.length ?? 0) > 0 ||
          (c.izlenecek_belirtiler_tr?.length ?? 0) > 0 ||
          (c.ne_zaman_tekrar_basvur_tr?.length ?? 0) > 0 ||
          (c.self_care_tr?.length ?? 0) > 0 ||
          !!c.aciliyet_notu_tr ||
          !!c.ipucu_tr;
        return (
          <div
            key={i}
            className={cn(
              "p-3.5 rounded-xl border bg-card",
              curated ? "border-blue-200 dark:border-blue-900/50" : "border-border",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-semibold text-sm truncate">{c.disease_label ?? "-"}</span>
                {curated && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded border border-blue-200 dark:border-blue-900/50 bg-blue-50 dark:bg-blue-950/30 text-blue-800 dark:text-blue-200 shrink-0">
                    Klinik bilgi
                  </span>
                )}
                {c.icd10 && (
                  <span className="text-[10px] font-mono text-muted-foreground shrink-0">
                    {c.icd10}
                  </span>
                )}
              </div>
              {pct !== null && (
                <span className="text-sm font-bold text-muted-foreground shrink-0">%{pct}</span>
              )}
            </div>
            {hasPrep && (
              <div className="mt-3 space-y-2 text-[13px]">
                {description && (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">Nedir?</div>
                    <div className="text-foreground/90 leading-normal">{description}</div>
                  </div>
                )}
                {c.ipucu_tr && (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">İpucu</div>
                    <div className="text-foreground/90">{c.ipucu_tr}</div>
                  </div>
                )}
                {c.doktora_sorulacak_sorular_tr?.length ? (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">
                      Doktora sorulacak sorular
                    </div>
                    <Bullets arr={c.doktora_sorulacak_sorular_tr} />
                  </div>
                ) : null}
                {c.izlenecek_belirtiler_tr?.length ? (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">
                      Takip edilecek belirtiler
                    </div>
                    <Bullets arr={c.izlenecek_belirtiler_tr} />
                  </div>
                ) : null}
                {c.ne_zaman_tekrar_basvur_tr?.length ? (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">
                      Ne zaman tekrar başvur
                    </div>
                    <Bullets arr={c.ne_zaman_tekrar_basvur_tr} />
                  </div>
                ) : null}
                {c.self_care_tr?.length ? (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">
                      Kendi kendine yapılabilecekler
                    </div>
                    <Bullets arr={c.self_care_tr} />
                  </div>
                ) : null}
                {c.aciliyet_notu_tr && (
                  <div>
                    <div className="text-[11px] font-bold text-muted-foreground mb-0.5">
                      Aciliyet notu
                    </div>
                    <div className="text-foreground/90">{c.aciliyet_notu_tr}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      {disclaimer && (
        <div className="text-[12px] italic text-muted-foreground pt-2">{disclaimer}</div>
      )}
    </div>
  );
}

export default async function SessionDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const locale = await getLocale();
  const { id } = await params;
  const sb = supabaseAdmin();

  const { data: session, error } = await sb
    .from("triage_sessions")
    .select("*")
    .eq("id", id)
    .single();

  const { data: feedback } = await sb
    .from("triage_feedback")
    .select("created_at,rating,comment,user_selected_specialty_id")
    .eq("session_id", id)
    .order("created_at", { ascending: false });

  const { data: events } = await sb
    .from("triage_events")
    .select("created_at,event_type,payload")
    .eq("session_id", id)
    .order("created_at", { ascending: true });

  // LLM calls scoped to this session. Joined by session_id on the
  // llm_calls table (populated by services/llm_nlu._log_llm_call).
  // Read-only; null/empty on pre-LLM-NLU sessions and on sessions
  // where LLM_NLU_ENABLED was false. Ordering matches triage_events
  // so the two timelines line up visually.
  const { data: llmCalls } = await sb
    .from("llm_calls")
    .select(
      "created_at,provider,model,success,error_type,nlu_source,latency_ms,input_tokens,output_tokens",
    )
    .eq("session_id", id)
    .order("created_at", { ascending: true });

  if (error) {
    return <div className="p-6">Error: {error.message}</div>;
  }

  return (
    <div className="p-6 max-w-[1000px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.sessions"), href: "/admin/sessions" }, { label: getText(locale, "sessions.sessionDetail") }]} />
      <div className="flex justify-between items-center">
        <Link href="/admin/sessions" className="text-muted-foreground no-underline text-sm">
          &larr; {getText(locale, "sessions.backToSessions")}
        </Link>
        <div className="flex items-center gap-4">
          {/* PDF export (Phase B7 U2). Plain anchor with download hint
              — browser handles the bytes stream + Save-As dialog. Using
              a real <a href> avoids needing client-side state; the
              route handler sets Content-Disposition so the filename
              flows from the backend. */}
          <a
            href={`/api/admin/session/${id}/export-pdf`}
            className="font-semibold text-primary no-underline hover:underline"
            download
          >
            📄 {getText(locale, "sessions.exportPdf")}
          </a>
          <Link href={`/admin/sessions/${id}/replay`} className="font-extrabold text-primary no-underline">
            Replay →
          </Link>
        </div>
      </div>

      <h1 className="text-2xl font-extrabold mt-3">Session Detail</h1>

      <div className="grid grid-cols-2 gap-3 mt-4">
        <div className="p-[18px] rounded-2xl border border-border bg-card">
          <div className="text-muted-foreground text-xs mb-1">Recommended Specialty</div>
          <div className="text-xl font-bold">{session.recommended_specialty_tr ?? "-"}</div>
          <div className="text-muted-foreground text-xs mt-1">{session.recommended_specialty_id ?? ""}</div>
        </div>
        <div className="p-[18px] rounded-2xl border border-border bg-card">
          <div className="text-muted-foreground text-xs mb-1">Confidence</div>
          <div className="text-xl font-bold">
            {session.confidence_label_tr ?? "-"}{" "}
            {typeof session.confidence_0_1 === "number" ? `(${Math.round(session.confidence_0_1 * 100)}%)` : ""}
          </div>
          {session.confidence_explain_tr && (
            <div className="text-muted-foreground mt-1.5 text-[13px]">{session.confidence_explain_tr}</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="p-3.5 rounded-xl border border-border bg-card">
          <div className="text-muted-foreground text-xs mb-1">Stop Reason</div>
          <div className="text-sm font-semibold">{session.stop_reason ?? "-"}</div>
        </div>
        <div className="p-3.5 rounded-xl border border-border bg-card">
          <div className="text-muted-foreground text-xs mb-1">Turn Index</div>
          <div className="text-sm font-semibold">{session.turn_index ?? 0}</div>
        </div>
      </div>

      <h2 className="text-lg font-bold mt-7">Input</h2>
      <div className="p-4 rounded-xl bg-primary text-primary-foreground text-sm leading-relaxed">
        {session.input_text ?? "(no input_text)"}
      </div>

      <h2 className="text-lg font-bold mt-6">Canonicals / Answers</h2>
      <Pretty data={{ user_canonicals_tr: session.user_canonicals_tr, answers: session.answers, asked_canonicals: session.asked_canonicals }} />

      <h2 className="text-lg font-bold mt-6">Why this specialty?</h2>
      <div className="p-4 rounded-2xl border border-border bg-card">
        <Bullets arr={session.why_specialty_tr} />
      </div>

      <h2 className="text-lg font-bold mt-6">Top Conditions</h2>
      <TopConditionsPanel conditions={session.top_conditions} />

      <h2 className="text-lg font-bold mt-6">Scoring Debug (rules)</h2>
      <Pretty data={session.specialty_scoring_debug} />

      <h2 className="text-lg font-bold mt-6">Confidence Debug</h2>
      <Pretty data={session.confidence_debug} />

      <h2 className="text-lg font-bold mt-6">LLM Çağrıları</h2>
      {llmCalls && llmCalls.length > 0 ? (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <table className="w-full text-[12px]">
            <thead className="text-left bg-muted">
              <tr>
                <th className="p-2.5">Zaman</th>
                <th className="p-2.5">Sağlayıcı / Model</th>
                <th className="p-2.5">Durum</th>
                <th className="p-2.5">NLU kaynağı</th>
                <th className="p-2.5 text-right">Gecikme</th>
                <th className="p-2.5 text-right">Giriş / Çıkış</th>
              </tr>
            </thead>
            <tbody>
              {(llmCalls as Array<{
                success?: boolean | null;
                created_at?: string | null;
                provider?: string | null;
                model?: string | null;
                error_type?: string | null;
                nlu_source?: string | null;
                latency_ms?: number | null;
                input_tokens?: number | null;
                output_tokens?: number | null;
              }>).map((c, i: number) => {
                const ok = c.success === true;
                const ts = c.created_at
                  ? new Date(c.created_at).toLocaleTimeString("tr-TR")
                  : "-";
                return (
                  <tr
                    key={i}
                    className={cn(
                      "border-t border-border",
                      !ok && "bg-red-50 dark:bg-red-950/20",
                    )}
                  >
                    <td className="p-2.5 whitespace-nowrap text-muted-foreground">
                      {ts}
                    </td>
                    <td className="p-2.5">
                      <div className="font-medium">{c.provider ?? "-"}</div>
                      <div className="text-muted-foreground text-[11px] font-mono">
                        {c.model ?? "-"}
                      </div>
                    </td>
                    <td className="p-2.5">
                      {ok ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-semibold">
                          ✓ OK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-700 dark:text-red-400 font-semibold">
                          ✗ {c.error_type ?? "err"}
                        </span>
                      )}
                    </td>
                    <td className="p-2.5 font-mono">{c.nlu_source ?? "-"}</td>
                    <td className="p-2.5 text-right whitespace-nowrap">
                      {typeof c.latency_ms === "number" ? `${c.latency_ms} ms` : "-"}
                    </td>
                    <td className="p-2.5 text-right whitespace-nowrap text-muted-foreground">
                      {typeof c.input_tokens === "number" || typeof c.output_tokens === "number"
                        ? `${c.input_tokens ?? "?"} / ${c.output_tokens ?? "?"}`
                        : "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-muted-foreground p-4 text-sm">
          Bu oturumda LLM NLU çağrısı yok (LLM_NLU_ENABLED kapalıydı veya
          sadece deterministic extraction çalıştı).
        </div>
      )}

      <h2 className="text-lg font-bold mt-6">Event Log</h2>
      {events && events.length > 0 ? (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          {events.map((e, i) => (
            <div
              key={i}
              className={cn("p-3 flex gap-3 items-start", i < events.length - 1 && "border-b border-border")}
            >
              <span className="text-[11px] text-muted-foreground whitespace-nowrap mt-0.5">
                {new Date(e.created_at).toLocaleTimeString("tr-TR")}
              </span>
              <span className="text-xs font-semibold text-foreground min-w-[160px]">{e.event_type}</span>
              <pre className="text-[11px] text-muted-foreground m-0 whitespace-pre-wrap flex-1">
                {JSON.stringify(e.payload, null, 1)}
              </pre>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-muted-foreground p-4">No events</div>
      )}

      <h2 className="text-lg font-bold mt-6">Feedback</h2>
      {feedback && feedback.length > 0 ? (
        <Pretty data={feedback} />
      ) : (
        <div className="text-muted-foreground p-4">No feedback yet</div>
      )}
    </div>
  );
}
