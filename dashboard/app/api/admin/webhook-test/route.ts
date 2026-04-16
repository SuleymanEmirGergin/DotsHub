import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
    const base = process.env.NEXT_PUBLIC_API_BASE!;
    const key = process.env.ADMIN_API_KEY!;

    const r = await fetch(`${base}/admin/webhook/test`, {
        method: "POST",
        headers: { "x-admin-key": key, "content-type": "application/json" },
        cache: "no-store",
    });

    const data = await r.json();
    return NextResponse.json(data, { status: r.status });
}
