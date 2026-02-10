import { NextResponse } from "next/server";

export async function GET() {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;

  const r = await fetch(`${base}/admin/stats/overview?lookback_limit=800`, {
    headers: { "x-admin-key": key },
    cache: "no-store",
  });

  const data = await r.json();
  return NextResponse.json(data, { status: r.status });
}
