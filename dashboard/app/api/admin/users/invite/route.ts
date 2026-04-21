import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy → backend `POST /admin/users/invite?email=&role=`.
 *
 * Grants admin role to an existing auth user resolved by email.
 * Returns 409 if no matching auth user exists; the UI surfaces the
 * "ask them to sign in once first" hint back to the operator.
 */
export async function POST(req: NextRequest) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;

  const url = new URL(req.url);
  const email = (url.searchParams.get("email") ?? "").trim();
  const role = url.searchParams.get("role") ?? "admin";

  if (!email) {
    return NextResponse.json({ error: "email is required" }, { status: 400 });
  }

  const qs = new URLSearchParams({ email, role }).toString();
  const r = await fetch(`${base}/admin/users/invite?${qs}`, {
    method: "POST",
    headers: { "x-admin-key": key, "content-type": "application/json" },
    cache: "no-store",
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
