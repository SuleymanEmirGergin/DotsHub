import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";

export const dynamic = "force-dynamic";

function Pretty({ data }: { data: unknown }) {
  return (
    <pre
      style={{
        background: "#fafafa",
        padding: 16,
        borderRadius: 12,
        overflowX: "auto",
        fontSize: 13,
        lineHeight: 1.6,
        border: "1px solid #eee",
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function Bullets({ arr }: { arr: unknown }) {
  if (!Array.isArray(arr) || arr.length === 0) {
    return <div style={{ color: "#999", padding: 8 }}>-</div>;
  }
  return (
    <ul style={{ marginTop: 8, paddingLeft: 18, marginBottom: 0 }}>
      {arr.map((x: unknown, i: number) => (
        <li key={i} style={{ marginBottom: 6, lineHeight: 1.5 }}>
          {String(x)}
        </li>
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
    return <div style={{ padding: 24 }}>Error: {error.message}</div>;
  }

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 1000,
        margin: "0 auto",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <a
          href="/admin/sessions"
          style={{ color: "#666", textDecoration: "none", fontSize: 14 }}
        >
          &larr; Back to sessions
        </a>
        <a
          href={`/admin/sessions/${id}/replay`}
          style={{ fontWeight: 800, color: "#111", textDecoration: "none" }}
        >
          Replay →
        </a>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 800, marginTop: 12 }}>
        Session Detail
      </h1>

      {/* Summary Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginTop: 16,
        }}
      >
        <div
          style={{
            padding: 18,
            borderRadius: 16,
            border: "1px solid #eee",
            backgroundColor: "#fff",
          }}
        >
          <div style={{ color: "#666", fontSize: 12, marginBottom: 4 }}>
            Recommended Specialty
          </div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            {session.recommended_specialty_tr ?? "-"}
          </div>
          <div style={{ color: "#999", fontSize: 12, marginTop: 4 }}>
            {session.recommended_specialty_id ?? ""}
          </div>
        </div>
        <div
          style={{
            padding: 18,
            borderRadius: 16,
            border: "1px solid #eee",
            backgroundColor: "#fff",
          }}
        >
          <div style={{ color: "#666", fontSize: 12, marginBottom: 4 }}>
            Confidence
          </div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            {session.confidence_label_tr ?? "-"}{" "}
            {typeof session.confidence_0_1 === "number"
              ? `(${Math.round(session.confidence_0_1 * 100)}%)`
              : ""}
          </div>
          {session.confidence_explain_tr && (
            <div style={{ color: "#666", marginTop: 6, fontSize: 13 }}>
              {session.confidence_explain_tr}
            </div>
          )}
        </div>
      </div>

      {/* Stop Reason + Turn */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginTop: 12,
        }}
      >
        <div
          style={{
            padding: 14,
            borderRadius: 12,
            border: "1px solid #eee",
            backgroundColor: "#fff",
          }}
        >
          <div style={{ color: "#666", fontSize: 12, marginBottom: 4 }}>
            Stop Reason
          </div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            {session.stop_reason ?? "-"}
          </div>
        </div>
        <div
          style={{
            padding: 14,
            borderRadius: 12,
            border: "1px solid #eee",
            backgroundColor: "#fff",
          }}
        >
          <div style={{ color: "#666", fontSize: 12, marginBottom: 4 }}>
            Turn Index
          </div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            {session.turn_index ?? 0}
          </div>
        </div>
      </div>

      {/* Input Text */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 28 }}>Input</h2>
      <div
        style={{
          padding: 16,
          borderRadius: 12,
          background: "#111",
          color: "white",
          fontSize: 14,
          lineHeight: 1.6,
        }}
      >
        {session.input_text ?? "(no input_text)"}
      </div>

      {/* Canonicals / Answers */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Canonicals / Answers
      </h2>
      <Pretty
        data={{
          user_canonicals_tr: session.user_canonicals_tr,
          answers: session.answers,
          asked_canonicals: session.asked_canonicals,
        }}
      />

      {/* Why this specialty? */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Why this specialty?
      </h2>
      <div
        style={{
          padding: 16,
          borderRadius: 16,
          border: "1px solid #eee",
          background: "#fff",
        }}
      >
        <Bullets arr={session.why_specialty_tr} />
      </div>

      {/* Top Conditions */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Top Conditions
      </h2>
      <Pretty data={session.top_conditions} />

      {/* Scoring Debug */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Scoring Debug (rules)
      </h2>
      <Pretty data={session.specialty_scoring_debug} />

      {/* Confidence Debug */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Confidence Debug
      </h2>
      <Pretty data={session.confidence_debug} />

      {/* Event Log */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Event Log
      </h2>
      {events && events.length > 0 ? (
        <div
          style={{
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #eee",
            overflow: "hidden",
          }}
        >
          {events.map((e, i) => (
            <div
              key={i}
              style={{
                padding: 12,
                borderBottom: i < events.length - 1 ? "1px solid #f3f3f3" : "none",
                display: "flex",
                gap: 12,
                alignItems: "flex-start",
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: "#999",
                  whiteSpace: "nowrap",
                  marginTop: 2,
                }}
              >
                {new Date(e.created_at).toLocaleTimeString("tr-TR")}
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#333",
                  minWidth: 160,
                }}
              >
                {e.event_type}
              </span>
              <pre
                style={{
                  fontSize: 11,
                  color: "#666",
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  flex: 1,
                }}
              >
                {JSON.stringify(e.payload, null, 1)}
              </pre>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: "#999", padding: 16 }}>No events</div>
      )}

      {/* Feedback */}
      <h2 style={{ fontSize: 18, fontWeight: 700, marginTop: 24 }}>
        Feedback
      </h2>
      {feedback && feedback.length > 0 ? (
        <Pretty data={feedback} />
      ) : (
        <div style={{ color: "#999", padding: 16 }}>No feedback yet</div>
      )}
    </div>
  );
}
