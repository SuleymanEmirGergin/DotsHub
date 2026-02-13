import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";

export const dynamic = "force-dynamic";

type ReplayEvent = {
    created_at: string;
    event_type: string;
    payload: Record<string, unknown>;
};

function Pill({ text }: { text: string }) {
    return (
        <span
            style={{
                display: "inline-block",
                padding: "4px 10px",
                borderRadius: 999,
                background: "#f2f2f2",
                fontSize: 12,
                fontWeight: 700,
            }}
        >
            {text}
        </span>
    );
}

function Pre({ obj }: { obj: unknown }) {
    return (
        <pre
            style={{
                marginTop: 10,
                background: "#0b0b0b",
                color: "white",
                padding: 12,
                borderRadius: 14,
                overflowX: "auto",
                fontSize: 12,
            }}
        >
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

function EventCard({ e }: { e: ReplayEvent }) {
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
                    t === "ENVELOPE_RESULT" ? `specialty=${specialtyName || "-"}` :
                        "";

    return (
        <div style={{ border: "1px solid var(--dash-border)", borderRadius: 16, padding: 14, background: "var(--dash-bg-card)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Pill text={label} />
                    <div style={{ fontWeight: 800 }}>{new Date(e.created_at).toLocaleString()}</div>
                </div>
                {turnIndex && <Pill text={`turn ${turnIndex}`} />}
            </div>

            {short && (
                <div style={{ marginTop: 10, color: "#222" }}>
                    {short}
                </div>
            )}

            {t === "ENVELOPE_QUESTION" && (
                <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    {canonical && <Pill text={`canonical: ${canonical}`} />}
                    {answerType && <Pill text={`type: ${answerType}`} />}
                </div>
            )}

            {t === "ENVELOPE_RESULT" && (
                <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    {specialtyName && <Pill text={`brans: ${specialtyName}`} />}
                    {confidenceLabel && <Pill text={`confidence: ${confidenceLabel}`} />}
                    {confidenceValue != null && <Pill text={`${Math.round(confidenceValue * 100)}%`} />}
                    {stopReason && <Pill text={`stop: ${stopReason}`} />}
                </div>
            )}

            <details style={{ marginTop: 10 }}>
                <summary style={{ cursor: "pointer", fontWeight: 800 }}>Payload</summary>
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
    const { id: sessionId } = await params;
    const sb = supabaseAdmin();

    const { data: session, error: sErr } = await sb
        .from("triage_sessions")
        .select("id, created_at, envelope_type, recommended_specialty_tr, confidence_label_tr, confidence_0_1, stop_reason, why_specialty_tr")
        .eq("id", sessionId)
        .maybeSingle();

    if (sErr) return <div style={{ padding: 24 }}>Error: {sErr.message}</div>;
    if (!session) return <div style={{ padding: 24 }}>Session not found.</div>;

    const { data: events, error: eErr } = await sb
        .from("triage_events")
        .select("created_at, event_type, payload")
        .eq("session_id", sessionId)
        .order("created_at", { ascending: true });

    if (eErr) return <div style={{ padding: 24 }}>Error: {eErr.message}</div>;

    return (
        <div style={{ padding: 24, fontFamily: "ui-sans-serif", background: "var(--dash-bg)", color: "var(--dash-text)", minHeight: "100vh" }}>
            <Breadcrumb items={[{ label: "Admin", href: "/admin/sessions" }, { label: "Sessions", href: "/admin/sessions" }, { label: "Replay" }]} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <div>
                    <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Session Replay</h1>
                    <div style={{ color: "var(--dash-text-muted)", marginTop: 6 }}>
                        {new Date(session.created_at).toLocaleString()} - {session.envelope_type} -{" "}
                        {session.recommended_specialty_tr ?? "-"} - {session.confidence_label_tr ?? "-"}{" "}
                        {typeof session.confidence_0_1 === "number" ? `(${Math.round(session.confidence_0_1 * 100)}%)` : ""}
                    </div>
                </div>

                <div style={{ display: "flex", gap: 10 }}>
                    <a href={`/admin/sessions/${sessionId}`} style={{ fontWeight: 800, color: "var(--dash-accent)", textDecoration: "none" }}>
                        Detail {"->"}
                    </a>
                    <a href="/admin/sessions" style={{ fontWeight: 800, color: "var(--dash-accent)", textDecoration: "none" }}>
                        Sessions {"->"}
                    </a>
                    <a href="/admin/analytics" style={{ fontWeight: 800, color: "var(--dash-accent)", textDecoration: "none" }}>
                        Analytics {"->"}
                    </a>
                </div>
            </div>

            {Array.isArray(session.why_specialty_tr) && session.why_specialty_tr.length > 0 && (
                <div style={{ marginTop: 14, border: "1px solid var(--dash-border)", borderRadius: 16, padding: 14, background: "var(--dash-bg-card)" }}>
                    <div style={{ fontSize: 12, color: "var(--dash-text-muted)" }}>Why this specialty?</div>
                    <ul style={{ marginTop: 10, paddingLeft: 18 }}>
                        {session.why_specialty_tr.map((x: string, i: number) => (
                            <li key={i} style={{ marginBottom: 6 }}>{String(x)}</li>
                        ))}
                    </ul>
                </div>
            )}

            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
                {(events ?? []).map((e, idx) => (
                    <EventCard key={idx} e={e as ReplayEvent} />
                ))}
            </div>
        </div>
    );
}
