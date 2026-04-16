import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";
import { proxyFetch } from "@/lib/api/proxy";

export async function GET(req: NextRequest) {
  await requireAdmin();

  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return NextResponse.json({ error: "API_BASE_NOT_CONFIGURED" }, { status: 500 });

  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const upstream = `${base}/admin/stats/risk_high_series${qs ? `?${qs}` : ""}`;

  const { data, status } = await proxyFetch(upstream, {
    headers: { "x-admin-key": process.env.ADMIN_API_KEY ?? "" },
    cache: "no-store",
  });
  return NextResponse.json(data, { status });
}
