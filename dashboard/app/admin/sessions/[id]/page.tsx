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

  if (error) {
    return <div className="p-6">Error: {error.message}</div>;
  }

  return (
    <div className="p-6 max-w-[1000px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.sessions"), href: "/admin/sessions" }, { label: getText(locale, "sessions.sessionDetail") }]} />
      <div className="flex justify-between items-center">
        <a href="/admin/sessions" className="text-muted-foreground no-underline text-sm">
          &larr; {getText(locale, "sessions.backToSessions")}
        </a>
        <a href={`/admin/sessions/${id}/replay`} className="font-extrabold text-primary no-underline">
          Replay →
        </a>
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
      <Pretty data={session.top_conditions} />

      <h2 className="text-lg font-bold mt-6">Scoring Debug (rules)</h2>
      <Pretty data={session.specialty_scoring_debug} />

      <h2 className="text-lg font-bold mt-6">Confidence Debug</h2>
      <Pretty data={session.confidence_debug} />

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
