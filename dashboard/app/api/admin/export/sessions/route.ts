import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";

function escapeCsvCell(s: unknown): string {
  if (s == null) return "";
  const str = String(s);
  if (/[",\n\r]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

export async function GET() {
  await requireAdmin();
  const sb = supabaseAdmin();
  const { data, error } = await sb
    .from("triage_sessions")
    .select("id,created_at,envelope_type,recommended_specialty_tr,confidence_label_tr,confidence_0_1,stop_reason")
    .order("created_at", { ascending: false })
    .limit(500);

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
