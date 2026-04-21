import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy → backend `/admin/users/{user_id}` (PATCH role, DELETE remove).
 *
 * Keeps ADMIN_API_KEY server-side only. The Next.js route params API
 * in App Router 14+ returns params as a Promise that must be awaited.
 */
type Params = { user_id: string };

export async function PATCH(
  req: NextRequest,
  ctx: { params: Promise<Params> },
) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;
  const { user_id } = await ctx.params;

  const url = new URL(req.url);
  const role = url.searchParams.get("role") ?? "";
  if (!role) {
    return NextResponse.json({ error: "role is required" }, { status: 400 });
  }

  const qs = new URLSearchParams({ role }).toString();
  const r = await fetch(
    `${base}/admin/users/${encodeURIComponent(user_id)}?${qs}`,
    {
      method: "PATCH",
      headers: { "x-admin-key": key, "content-type": "application/json" },
      cache: "no-store",
    },
  );

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}

export async function DELETE(
  _req: NextRequest,
  ctx: { params: Promise<Params> },
) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;
  const { user_id } = await ctx.params;

  const r = await fetch(
    `${base}/admin/users/${encodeURIComponent(user_id)}`,
    {
      method: "DELETE",
      headers: { "x-admin-key": key, "content-type": "application/json" },
      cache: "no-store",
    },
  );

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
