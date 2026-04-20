import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy → backend `/admin/sessions/{id}/export-pdf` (Phase B7 U2).
 *
 * Streams the PDF bytes through with Content-Disposition preserved
 * so the browser "Save as…" dialog shows the filename the backend
 * assigned.
 *
 * Forwards errors (404 "session not found", 401 "unauthorized")
 * as JSON so the dashboard UI can surface a meaningful message
 * instead of a broken download.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ session_id: string }> },
) {
  const { session_id } = await params;
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;
  const upstream = `${base}/admin/sessions/${session_id}/export-pdf`;

  const r = await fetch(upstream, {
    headers: { "x-admin-key": key },
    cache: "no-store",
  });

  if (!r.ok) {
    // Backend returns JSON `{ detail: "..." }` on HTTPException;
    // surface that to the caller with the original status.
    const errorText = await r.text();
    return new NextResponse(errorText, {
      status: r.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Happy path: stream bytes through, preserve Content-Disposition
  // so the user's browser picks up the server-assigned filename.
  const body = await r.arrayBuffer();
  const disposition =
    r.headers.get("content-disposition") ??
    `attachment; filename="triaige-session-${session_id}.pdf"`;
  return new NextResponse(body, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": disposition,
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}
