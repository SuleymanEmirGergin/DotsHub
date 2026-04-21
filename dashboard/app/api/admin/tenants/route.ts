import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Proxy for POST /v1/admin/tenants — creates a new tenant.
// The browser talks to this Next.js route; the route injects the
// admin key (server-side env) and forwards to the FastAPI backend.
// This keeps ADMIN_API_KEY out of the client bundle.
export async function POST(req: NextRequest) {
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
    const r = await fetch(`${base.replace(/\/+$/, "")}/v1/admin/tenants`, {
      method: "POST",
      headers: {
        "x-admin-key": key,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    });
    const data = await r.json().catch(() => ({}));
    return NextResponse.json(data, { status: r.status });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "upstream error";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
