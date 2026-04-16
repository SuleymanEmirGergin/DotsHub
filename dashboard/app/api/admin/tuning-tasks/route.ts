import { NextRequest, NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";

/**
 * GET /api/admin/tuning-tasks — proxy to backend (tenant-scoped list).
 * Query: status, type, sort, order, limit.
 */
export async function GET(req: NextRequest) {
  await requireAdmin();
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_API_BASE or ADMIN_API_KEY not configured" },
      { status: 500 }
    );
  }

  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();
  const upstream = `${base.replace(/\/+$/, "")}/v1/admin/tuning-tasks${qs ? `?${qs}` : ""}`;

  const r = await fetch(upstream, {
    headers: { "x-admin-key": key },
    cache: "no-store",
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
