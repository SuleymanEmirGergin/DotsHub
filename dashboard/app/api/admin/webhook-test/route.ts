import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";
import { proxyFetch } from "@/lib/api/proxy";

export async function POST(req: NextRequest) {
  await requireAdmin();

  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return NextResponse.json({ error: "API_BASE_NOT_CONFIGURED" }, { status: 500 });

  const { data, status } = await proxyFetch(`${base}/admin/webhook/test`, {
    method: "POST",
    headers: { "x-admin-key": process.env.ADMIN_API_KEY ?? "", "content-type": "application/json" },
    cache: "no-store",
  });
  return NextResponse.json(data, { status });
}
