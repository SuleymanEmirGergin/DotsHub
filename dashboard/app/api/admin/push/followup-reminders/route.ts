import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy → backend `POST /admin/push/followup-reminders`.
 *
 * Triggers the follow-up reminder push batch. Keeps ADMIN_API_KEY
 * server-side only (Vercel env, never exposed to the browser) — same
 * pattern as the other `/api/admin/*` routes.
 *
 * Query params forwarded: `hours_min` (default 20), `hours_max`
 * (default 48). Backend clamps to [1,72] / [2,168] and also enforces
 * hours_min < hours_max.
 *
 * Response shape (success): `{ sent, skipped_feedback, skipped_no_token,
 * candidates }` — see backend app/push.py::send_followup_reminders.
 */
export async function POST(req: NextRequest) {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const key = process.env.ADMIN_API_KEY!;

  const url = new URL(req.url);
  const hoursMin = url.searchParams.get("hours_min") ?? "20";
  const hoursMax = url.searchParams.get("hours_max") ?? "48";

  const qs = new URLSearchParams({
    hours_min: hoursMin,
    hours_max: hoursMax,
  }).toString();

  const r = await fetch(
    `${base}/admin/push/followup-reminders?${qs}`,
    {
      method: "POST",
      headers: { "x-admin-key": key, "content-type": "application/json" },
      cache: "no-store",
    },
  );

  const data = await r.json().catch(() => ({}));
  return NextResponse.json(data, { status: r.status });
}
