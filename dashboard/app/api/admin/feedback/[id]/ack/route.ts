import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Proxy for POST /v1/admin/feedback/{id}/ack. Admin key stays
// server-side; browser talks only to this same-origin route.
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_API_BASE veya ADMIN_API_KEY tanımlı değil." },
      { status: 500 },
    );
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  try {
    const r = await fetch(
      `${base.replace(/\/+$/, "")}/v1/admin/feedback/${encodeURIComponent(id)}/ack`,
      {
        method: "POST",
        headers: {
          "x-admin-key": key,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(10000),
      },
    );
    const data = await r.json().catch(() => ({}));
    return NextResponse.json(data, { status: r.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? "upstream error" }, { status: 502 });
  }
}
