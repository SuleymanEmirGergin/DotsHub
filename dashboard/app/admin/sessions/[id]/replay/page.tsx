import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";

export const dynamic = "force-dynamic";

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

function EventCard({ e }: { e: { created_at: string; event_type: string; payload: Record<string, unknown> } }) {
    const t = String(e.event_type || "");
    const payload = e.payload ?? {};

    const label =
        t.startsWith("ENVELOPE_") ? t.replace("ENVELOPE_", "") :
            t === "USER_MESSAGE" ? "USER" :
                t === "ANSWER_RECEIVED" ? "ANSWER" :
                    t;

    const short =
        t === "USER_MESSAGE" ? (payload.text ? String(payload.text).slice(0, 120) : "") :
            t === "ENVELOPE_QUESTION" ? (payload.question_tr ? String(payload.question_tr).slice(0, 120) : "") :
                t === "ANSWER_RECEIVED" ? `${payload.canonical}: ${payload.value}` :
                    t === "ENVELOPE_RESULT" ? `specialty=${(payload?.recommended_specialty as Record<string, unknown>)?.name_tr ?? "-"}` :
                        "";

    return (
        <div style={{ border: "1px solid #eee", borderRadius: 16, padding: 14, background: "white" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Pill text={label} />
                    <div style={{ fontWeight: 800 }}>{new Date(e.created_at).toLocaleString()}</div>
                </div>
                {(payload as Record<string, unknown>)?._turn_index != null && <Pill text={`turn ${(payload as Record<string, unknown>)._turn_index}`} />}
            </div>

            {short && (
                <div style={{ marginTop: 10, color: "#222" }}>
                    {short}
                </div>
            )}

            {t === "ENVELOPE_QUESTION" && (
                <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    {payload.canonical && <Pill text={`canonical: ${payload.canonical}`} />}
                    {payload.answer_type && <Pill text={`type: ${payload.answer_type}`} />}
                </div>
            )}

            {t === "ENVELOPE_RESULT" && (
                <div style={{ marginTop: 10, display: "flex", gap: 10, flexWrap: "wrap" }}>
                    {(payload?.recommended_specialty as Record<string, unknown>)?.name_tr && <Pill text={`branş: ${(payload.recommended_specialty as Record<string, unknown>).name_tr}`} />}
                    {payload.confidence_label_tr && <Pill text={`confidence: ${payload.confidence_label_tr}`} />}
                    {typeof payload.confidence_0_1 === "number" && <Pill text={`${Math.round(payload.confidence_0_1 * 100)}%`} />}
                    {payload.stop_reason && <Pill text={`stop: ${payload.stop_reason}`} />}
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
        <div style={{ padding: 24, fontFamily: "ui-sans-serif", background: "#fafafa", minHeight: "100vh" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <div>
                    <h1 style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>Session Replay</h1>
                    <div style={{ color: "#666", marginTop: 6 }}>
                        {new Date(session.created_at).toLocaleString()} • {session.envelope_type} •{" "}
                        {session.recommended_specialty_tr ?? "-"} •{" "}
                        {session.confidence_label_tr ?? "-"}{" "}
                        {typeof session.confidence_0_1 === "number" ? `(${Math.round(session.confidence_0_1 * 100)}%)` : ""}
                    </div>
                </div>

                <div style={{ display: "flex", gap: 10 }}>
                    <a href={`/admin/sessions/${sessionId}`} style={{ fontWeight: 800, color: "#111", textDecoration: "none" }}>
                        Detail →
                    </a>
                    <a href="/admin/sessions" style={{ fontWeight: 800, color: "#111", textDecoration: "none" }}>
                        Sessions →
                    </a>
                    <a href="/admin/analytics" style={{ fontWeight: 800, color: "#111", textDecoration: "none" }}>
                        Analytics →
                    </a>
                </div>
            </div>

            {Array.isArray(session.why_specialty_tr) && session.why_specialty_tr.length > 0 && (
                <div style={{ marginTop: 14, border: "1px solid #eee", borderRadius: 16, padding: 14, background: "white" }}>
                    <div style={{ fontSize: 12, color: "#666" }}>Why this specialty?</div>
                    <ul style={{ marginTop: 10, paddingLeft: 18 }}>
                        {session.why_specialty_tr.map((x: string, i: number) => (
                            <li key={i} style={{ marginBottom: 6 }}>{String(x)}</li>
                        ))}
                    </ul>
                </div>
            )}

            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
                {(events ?? []).map((e, idx) => (
                    <EventCard key={idx} e={e as { created_at: string; event_type: string; payload: Record<string, unknown> }} />
                ))}
            </div>
        </div>
    );
}
