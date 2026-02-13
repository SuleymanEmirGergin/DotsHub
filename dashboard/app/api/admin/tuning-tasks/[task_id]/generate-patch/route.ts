import { NextRequest, NextResponse } from "next/server";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ task_id: string }> }
) {
  const { task_id } = await params;
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

  const upstream = `${base.replace(/\/+$/, "")}/v1/admin/tuning-tasks/${task_id}/generate-patch`;
  const response = await fetch(upstream, {
    method: "POST",
    headers: { "x-admin-key": key, "Content-Type": "application/json" },
    cache: "no-store",
  });

  const bodyText = await response.text();
  let body: unknown = {};

  if (bodyText) {
    try {
      body = JSON.parse(bodyText);
    } catch {
      body = { detail: bodyText };
    }
  }

  return NextResponse.json(body, { status: response.status });
}
