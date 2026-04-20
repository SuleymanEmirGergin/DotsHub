import { NextResponse } from "next/server";

/**
 * Proxy → backend /admin/stats/daily-summary (Phase B7).
 *
 * Keeps the ADMIN_API_KEY secret server-side (Vercel env, never
 * exposed to the browser). Matches the contract documented in
 * backend/app/admin_v5.py::daily_summary.
 *
 * ?days query is forwarded unchanged; backend clamps to [1, 30].
 */
export async function GET(req: Request) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;

  const url = new URL(req.url);
  const days = url.searchParams.get("days") ?? "7";

  const r = await fetch(
    `${base}/admin/stats/daily-summary?days=${encodeURIComponent(days)}`,
    {
      headers: { "x-admin-key": key },
      cache: "no-store",
    }
  );

  const data = await r.json();
  return NextResponse.json(data, { status: r.status });
}
