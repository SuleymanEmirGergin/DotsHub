import { cookies } from "next/headers";
import Link from "next/link";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { Breadcrumb } from "@/app/components/Breadcrumb";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

type ReplayEvent = {
  created_at: string;
  event_type: string;
  payload: Record<string, unknown>;
};

function Pill({ text }: { text: string }) {
  return (
    <span className="inline-block py-1 px-2.5 rounded-full bg-muted text-foreground text-xs font-bold">
      {text}
    </span>
  );
}

function Pre({ obj }: { obj: unknown }) {
  return (
    <pre className="mt-2.5 bg-zinc-900 text-white p-3 rounded-xl overflow-x-auto text-xs">
      {JSON.stringify(obj, null, 2)}
    </pre>
  );
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asPrintable(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function EventCard({ e, locale }: { e: ReplayEvent; locale: Locale }) {
  const t = String(e.event_type || "");
  const payload = toRecord(e.payload);
  const canonical = asString(payload.canonical);
  const answerType = asString(payload.answer_type);
  const confidenceLabel = asString(payload.confidence_label_tr);
  const confidenceValue = typeof payload.confidence_0_1 === "number" ? payload.confidence_0_1 : null;
  const stopReason = asString(payload.stop_reason);
  const turnIndex = asPrintable(payload._turn_index);
  const specialtyRecord = toRecord(payload.recommended_specialty);
  const specialtyName = asString(specialtyRecord.name_tr);
  const shortUserText = asString(payload.text).slice(0, 120);
  const shortQuestionText = asString(payload.question_tr).slice(0, 120);
  const answerValue = asPrintable(payload.value);

  const label =
    t.startsWith("ENVELOPE_") ? t.replace("ENVELOPE_", "") :
    t === "USER_MESSAGE" ? "USER" :
    t === "ANSWER_RECEIVED" ? "ANSWER" :
    t;

  const short =
    t === "USER_MESSAGE" ? shortUserText :
    t === "ENVELOPE_QUESTION" ? shortQuestionText :
    t === "ANSWER_RECEIVED" ? `${canonical}: ${answerValue}` :
    t === "ENVELOPE_RESULT" ? `${getText(locale, "sessionReplay.specialty")}=${specialtyName || "-"}` :
    "";

  return (
    <div className="border border-border rounded-2xl p-3.5 bg-card">
      <div className="flex justify-between gap-3 items-center">
        <div className="flex gap-2.5 items-center">
          <Pill text={label} />
          <div className="font-extrabold">{new Date(e.created_at).toLocaleString()}</div>
        </div>
        {turnIndex && <Pill text={`${getText(locale, "sessionReplay.turn")} ${turnIndex}`} />}
      </div>

      {short && <div className="mt-2.5 text-foreground">{short}</div>}

      {t === "ENVELOPE_QUESTION" && (
        <div className="mt-2.5 flex gap-2.5 flex-wrap">
          {canonical && <Pill text={`${getText(locale, "sessionReplay.canonical")}: ${canonical}`} />}
          {answerType && <Pill text={`${getText(locale, "sessionReplay.type")}: ${answerType}`} />}
        </div>
      )}

      {t === "ENVELOPE_RESULT" && (
        <div className="mt-2.5 flex gap-2.5 flex-wrap">
          {specialtyName && <Pill text={`${getText(locale, "sessionReplay.specialty")}: ${specialtyName}`} />}
          {confidenceLabel && <Pill text={`${getText(locale, "sessionReplay.confidence")}: ${confidenceLabel}`} />}
          {confidenceValue != null && <Pill text={`${Math.round(confidenceValue * 100)}%`} />}
          {stopReason && <Pill text={`${getText(locale, "sessionReplay.stop")}: ${stopReason}`} />}
        </div>
      )}

      <details className="mt-2.5">
        <summary className="cursor-pointer font-extrabold">{getText(locale, "sessionReplay.payload")}</summary>
        <Pre obj={payload} />
      </details>
    </div>
  );
}

export default async function SessionReplayPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const locale = await getLocale();
  const { id: sessionId } = await params;
  const sb = supabaseAdmin();

  const { data: session, error: sErr } = await sb
    .from("triage_sessions")
    .select("id, created_at, envelope_type, recommended_specialty_tr, confidence_label_tr, confidence_0_1, stop_reason, why_specialty_tr")
    .eq("id", sessionId)
    .maybeSingle();

  if (sErr) return <div className="p-6">{getText(locale, "sessionReplay.error")} {sErr.message}</div>;
  if (!session) return <div className="p-6">{getText(locale, "sessionReplay.sessionNotFound")}</div>;

  const { data: events, error: eErr } = await sb
    .from("triage_events")
    .select("created_at, event_type, payload")
    .eq("session_id", sessionId)
    .order("created_at", { ascending: true });

  if (eErr) return <div className="p-6">{getText(locale, "sessionReplay.error")} {eErr.message}</div>;

  return (
    <div className="p-6 font-sans bg-background text-foreground min-h-screen">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/sessions" }, { label: getText(locale, "nav.sessions"), href: "/admin/sessions" }, { label: getText(locale, "tuningTasks.replay") }]} />
      <div className="flex justify-between items-center gap-3">
        <div>
          <h1 className="text-[26px] font-black m-0">{getText(locale, "sessionReplay.title")}</h1>
          <div className="text-muted-foreground mt-1.5">
            {new Date(session.created_at).toLocaleString()} - {session.envelope_type} -{" "}
            {session.recommended_specialty_tr ?? "-"} - {session.confidence_label_tr ?? "-"}{" "}
            {typeof session.confidence_0_1 === "number" ? `(${Math.round(session.confidence_0_1 * 100)}%)` : ""}
          </div>
        </div>
        <div className="flex gap-2.5">
          <Link href={`/admin/sessions/${sessionId}`} className="font-extrabold text-primary no-underline">
            {getText(locale, "sessionReplay.detailLink")}
          </Link>
          <Link href="/admin/sessions" className="font-extrabold text-primary no-underline">
            {getText(locale, "sessionReplay.sessionsLink")}
          </Link>
          <Link href="/admin/analytics" className="font-extrabold text-primary no-underline">
            {getText(locale, "sessionReplay.analyticsLink")}
          </Link>
        </div>
      </div>

      {Array.isArray(session.why_specialty_tr) && session.why_specialty_tr.length > 0 && (
        <div className="mt-3.5 border border-border rounded-2xl p-3.5 bg-card">
          <div className="text-xs text-muted-foreground">{getText(locale, "sessionReplay.whySpecialty")}</div>
          <ul className="mt-2.5 pl-[18px]">
            {session.why_specialty_tr.map((x: string, i: number) => (
              <li key={i} className="mb-1.5">{String(x)}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3.5 flex flex-col gap-3">
        {(events ?? []).map((e, idx) => (
          <EventCard key={idx} e={e as ReplayEvent} locale={locale} />
        ))}
      </div>
    </div>
  );
}
