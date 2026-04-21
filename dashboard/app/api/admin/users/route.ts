import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy → backend `/admin/users` (GET list, POST legacy-add).
 *
 * GET returns `{ users: [...] }` from admin_users.
 * POST is the legacy direct-add path (email + user_id + role) — kept
 * so existing ops scripts keep working; the dashboard UI uses
 * `/api/admin/users/invite` instead.
 *
 * Keeps ADMIN_API_KEY server-side only.
 */
export async function GET() {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;

  const r = await fetch(`${base}/admin/users`, {
    headers: { "x-admin-key": key },
    cache: "no-store",
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}

export async function POST(req: NextRequest) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;

  const url = new URL(req.url);
  // Forward the query params the backend expects: email, user_id, role.
  const qs = url.searchParams.toString();

  const r = await fetch(`${base}/admin/users?${qs}`, {
    method: "POST",
    headers: { "x-admin-key": key, "content-type": "application/json" },
    cache: "no-store",
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
