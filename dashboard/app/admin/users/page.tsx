import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

export default async function AdminUsersPage() {
  const { role } = await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);
  const sb = supabaseAdmin();

  const { data: users } = await sb
    .from("admin_users")
    .select("id,user_id,email,role,created_at")
    .order("created_at", { ascending: false });

  return (
    <div className="p-6 max-w-[900px] mx-auto">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/analytics" }, { label: t("users.breadcrumb") }]} />
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-extrabold text-foreground m-0">{t("users.title")}</h1>
        <span className="py-1 px-3 rounded-lg bg-accent text-muted-foreground text-xs font-semibold">
          {t("users.yourRole")}: {role}
        </span>
      </div>
      <div className="border border-border rounded-2xl overflow-hidden bg-card">
        <table className="w-full border-collapse text-sm text-foreground">
          <thead>
            <tr className="bg-accent text-left">
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">{t("users.email")}</th>
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">{t("users.role")}</th>
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">{t("users.createdAt")}</th>
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">{t("users.userId")}</th>
            </tr>
          </thead>
          <tbody>
            {(users ?? []).length === 0 && (
              <tr>
                <td colSpan={4} className="p-10 text-center text-muted-foreground">
                  {t("users.noUsers")}
                  <br />
                  <span className="text-xs">{t("users.noUsersHint")}</span>
                </td>
              </tr>
            )}
            {(users ?? []).map((u: any) => (
              <tr key={u.id} className="border-t border-border">
                <td className="p-3.5"><strong>{u.email}</strong></td>
                <td className="p-3.5">
                  <span className={u.role === "super_admin" ? "py-0.5 px-2 rounded-md bg-violet-100 text-violet-600 dark:bg-violet-900/40 dark:text-violet-300 font-semibold text-xs" : "py-0.5 px-2 rounded-md bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300 font-semibold text-xs"}>
                    {u.role}
                  </span>
                </td>
                <td className="p-3.5">{new Date(u.created_at).toLocaleDateString(locale === "en" ? "en-US" : "tr-TR")}</td>
                <td className="p-3.5 font-mono text-xs">{u.user_id?.slice(0, 8)}...</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground mt-4">{t("users.createHint")}</p>
    </div>
  );
}
