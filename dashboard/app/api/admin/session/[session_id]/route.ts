import { NextRequest, NextResponse } from "next/server";

export async function GET(
    _req: NextRequest,
    { params }: { params: { session_id: string } }
) {
    const base = process.env.NEXT_PUBLIC_API_BASE!;
    const key = process.env.ADMIN_API_KEY!;
    const upstream = `${base}/admin/sessions/${params.session_id}`;

    const r = await fetch(upstream, {
        headers: { "x-admin-key": key },
        cache: "no-store",
    });

    const data = await r.json();
    return NextResponse.json(data, { status: r.status });
}
