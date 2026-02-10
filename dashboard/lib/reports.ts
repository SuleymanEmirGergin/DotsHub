import { supabaseServerAuthed } from "./supabaseServerAuthed";
import { supabaseAdmin } from "./supabaseServer";

/**
 * List reports from Supabase Storage "reports" bucket.
 * Uses admin client (service role) for storage operations.
 */
export async function listReports(limit = 20) {
  const sb = supabaseAdmin();
  const { data, error } = await sb.storage.from("reports").list("", {
    limit,
    sortBy: { column: "created_at", order: "desc" },
  });
  if (error) throw new Error(error.message);
  return data ?? [];
}

/**
 * Get a signed URL for a report file (valid for 60 seconds).
 */
export async function getSignedReportUrl(path: string) {
  const sb = supabaseAdmin();
  const { data, error } = await sb.storage
    .from("reports")
    .createSignedUrl(path, 60);
  if (error) throw new Error(error.message);
  return data.signedUrl;
}

/**
 * Fetch JSON content from a signed URL.
 */
export async function fetchJsonFromSignedUrl(url: string) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch report");
  return await res.json();
}
