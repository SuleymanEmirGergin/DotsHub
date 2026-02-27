import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
    const base = process.env.NEXT_PUBLIC_API_BASE!;
    const key = process.env.ADMIN_API_KEY!;
    const url = new URL(req.url);

    const qs = url.searchParams.toString();
    const upstream = `${base}/admin/stats/overview${qs ? `?${qs}` : ""}`;

    const r = await fetch(upstream, {
        headers: { "x-admin-key": key },
        cache: "no-store",
    });

    const data = await r.json();
    return NextResponse.json(data, { status: r.status });
}
