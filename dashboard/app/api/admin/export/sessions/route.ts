import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";

function escapeCsvCell(s: unknown): string {
  if (s == null) return "";
  const str = String(s);
  if (/[",\n\r]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

export async function GET(request: Request) {
  await requireAdmin();
  const { searchParams } = new URL(request.url);
  const feedback = searchParams.get("feedback");
  const envelopeType = searchParams.get("envelope_type");

  const sb = supabaseAdmin();

  let sessionIds: string[] | null = null;
  if (feedback === "down" || feedback === "up") {
    const { data: fb } = await sb
      .from("triage_feedback")
      .select("session_id")
      .eq("rating", feedback)
      .limit(2000);
    sessionIds = Array.from(new Set((fb ?? []).map((x: { session_id: string }) => x.session_id).filter(Boolean)));
    if (sessionIds.length === 0) sessionIds = ["00000000-0000-0000-0000-000000000000"];
  }

  let q = sb
    .from("triage_sessions")
    .select("id,created_at,envelope_type,recommended_specialty_tr,confidence_label_tr,confidence_0_1,stop_reason")
    .order("created_at", { ascending: false })
    .limit(500);

  if (sessionIds) q = q.in("id", sessionIds);
  if (envelopeType && ["RESULT", "EMERGENCY", "QUESTION", "SAME_DAY", "ERROR"].includes(envelopeType)) {
    q = q.eq("envelope_type", envelopeType);
  }

  const { data, error } = await q;

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const headers = ["id", "created_at", "envelope_type", "recommended_specialty_tr", "confidence_label_tr", "confidence_0_1", "stop_reason"];
  const rows = (data ?? []).map((r: any) =>
    headers.map((h) => escapeCsvCell(r[h])).join(",")
  );
  const csv = [headers.join(","), ...rows].join("\n");

  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="sessions-${new Date().toISOString().slice(0, 10)}.csv"`,
    },
  });
}
