import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";
import { proxyFetch } from "@/lib/api/proxy";

export async function GET() {
  await requireAdmin();

  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return NextResponse.json({ error: "API_BASE_NOT_CONFIGURED" }, { status: 500 });

  const { data, status } = await proxyFetch(`${base}/admin/stats/overview?lookback_limit=800`, {
    headers: { "x-admin-key": process.env.ADMIN_API_KEY ?? "" },
    cache: "no-store",
  });
  return NextResponse.json(data, { status });
}
