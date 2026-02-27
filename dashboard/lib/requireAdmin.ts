import { redirect } from "next/navigation";
import { supabaseServerAuthed } from "./supabaseServerAuthed";

/**
 * Gate for admin pages — checks Supabase auth session + admin_users table.
 * Redirects to /login if not authenticated or not an admin.
 *
 * Falls back to allowing access if NEXT_PUBLIC_SUPABASE_ANON_KEY is not set
 * (development mode without Supabase Auth configured).
 */
export async function requireAdmin() {
  // If Supabase Auth not configured, skip gate (dev mode)
  if (!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) return { user: null, role: "admin" };

  const sb = await supabaseServerAuthed();
  const {
    data: { user },
  } = await sb.auth.getUser();

  if (!user) redirect("/login");

  const { data: adminRow } = await sb
    .from("admin_users")
    .select("role")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!adminRow) redirect("/login?e=not_admin");

  return { user, role: adminRow.role as string };
}
