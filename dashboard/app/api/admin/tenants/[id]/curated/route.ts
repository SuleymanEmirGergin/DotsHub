import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// DELETE proxies /v1/admin/tenants/{id} (no /curated suffix — the
// delete is of the whole tenant, not just the catalog sub-resource).
// Kept in this file for locality with GET/PUT despite the path
// mismatch; the route handler file name is shared purely for
// co-location. Next.js [id] segment carries the tenant.
export async function DELETE(
  _req: NextRequest,
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
  try {
    const r = await fetch(
      `${base.replace(/\/+$/, "")}/v1/admin/tenants/${encodeURIComponent(id)}`,
      {
        method: "DELETE",
        headers: { "x-admin-key": key },
        signal: AbortSignal.timeout(10000),
      },
    );
    const data = await r.json().catch(() => ({}));
    return NextResponse.json(data, { status: r.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? "upstream error" }, { status: 502 });
  }
}

// Proxy for GET / PUT /v1/admin/tenants/{id}/curated
// Admin key stays server-side; the browser talks only to this route.

export async function GET(
  _req: NextRequest,
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
  try {
    const r = await fetch(
      `${base.replace(/\/+$/, "")}/v1/admin/tenants/${encodeURIComponent(id)}/curated`,
      {
        headers: { "x-admin-key": key },
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      },
    );
    const data = await r.json().catch(() => ({}));
    return NextResponse.json(data, { status: r.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? "upstream error" }, { status: 502 });
  }
}

export async function PUT(
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
    return NextResponse.json({ error: "Geçersiz JSON." }, { status: 400 });
  }
  try {
    const r = await fetch(
      `${base.replace(/\/+$/, "")}/v1/admin/tenants/${encodeURIComponent(id)}/curated`,
      {
        method: "PUT",
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
