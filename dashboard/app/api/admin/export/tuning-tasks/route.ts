import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/requireAdmin";

/**
 * GET /api/admin/export/tuning-tasks — proxy to backend (tenant-scoped CSV export).
 * Query: status, type.
 */
export async function GET(request: Request) {
  await requireAdmin();
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_API_BASE or ADMIN_API_KEY not configured" },
      { status: 500 }
    );
  }

  const { searchParams } = new URL(request.url);
  const qs = searchParams.toString();
  const upstream = `${base.replace(/\/+$/, "")}/v1/admin/tuning-tasks/export${qs ? `?${qs}` : ""}`;

  const r = await fetch(upstream, {
    headers: { "x-admin-key": key },
    cache: "no-store",
  });

  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    return NextResponse.json(err, { status: r.status });
  }

  const csv = await r.text();
  const disposition = r.headers.get("content-disposition") ?? `attachment; filename="tuning-tasks-${new Date().toISOString().slice(0, 10)}.csv"`;

  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": disposition,
    },
  });
}
