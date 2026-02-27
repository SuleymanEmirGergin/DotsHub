import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy POST to backend admin generate-patch. Uses ADMIN_API_KEY so the
 * browser does not need to send the key; the server adds it.
 */
export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;

  if (!base) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_API_BASE not configured" },
      { status: 500 }
    );
  }
  if (!key) {
    return NextResponse.json(
      { error: "ADMIN_API_KEY not configured" },
      { status: 500 }
    );
  }

  const url = `${base.replace(/\/+$/, "")}/v1/admin/tuning-tasks/${taskId}/generate-patch`;
  const r = await fetch(url, {
    method: "POST",
    headers: { "X-API-Key": key, "Content-Type": "application/json" },
    cache: "no-store",
  });

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
