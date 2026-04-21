import { cookies } from "next/headers";
import { requireAdmin } from "@/lib/requireAdmin";
import { supabaseAdmin } from "@/lib/supabaseServer";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import UsersTable, { type AdminUserRow } from "./UsersTable";

export const dynamic = "force-dynamic";

async function getLocale(): Promise<Locale> {
  const store = await cookies();
  return store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
}

/**
 * /admin/users — admin user management.
 *
 * Server-rendered shell: runs the role gate, fetches initial rows,
 * then hands off to the <UsersTable /> client component which owns
 * all interactivity (invite form, role change, remove). Super-admin
 * gating happens both server-side (we pass the `role`) and in the
 * client (actions are hidden for role !== "super_admin").
 *
 * Data source is still ``supabaseAdmin()`` direct-query — we don't
 * need to pay the hop through the backend proxy just to list, and
 * the service-role key is already available in this server context.
 * Mutations (invite/patch/delete) DO go through the proxy because
 * they require backend logic (auth.users resolution for invite, role
 * validation, etc).
 */
export default async function AdminUsersPage() {
  const { role, user } = await requireAdmin();
  const locale = await getLocale();
  const t = (key: string) => getText(locale, key);
  const sb = supabaseAdmin();

  const { data: users } = await sb
    .from("admin_users")
    .select("id,user_id,email,role,created_at")
    .order("created_at", { ascending: false });

  const rows = (users ?? []) as AdminUserRow[];

  // Bundle all i18n strings UsersTable needs into a single prop so the
  // client never has to do its own getText lookup — keeps the page
  // SSR-safe with no hydration mismatch on locale.
  const i18n = {
    email: t("users.email"),
    role: t("users.role"),
    createdAt: t("users.createdAt"),
    userId: t("users.userId"),
    noUsers: t("users.noUsers"),
    noUsersHint: t("users.noUsersHint"),
    roleAdmin: t("users.roleAdmin"),
    roleSuperAdmin: t("users.roleSuperAdmin"),
    inviteButton: t("users.inviteButton"),
    inviteTitle: t("users.inviteTitle"),
    inviteDescription: t("users.inviteDescription"),
    inviteEmailPlaceholder: t("users.inviteEmailPlaceholder"),
    inviteSubmit: t("users.inviteSubmit"),
    inviteCancel: t("users.inviteCancel"),
    inviteRolePrompt: t("users.inviteRolePrompt"),
    inviteSuccess: t("users.inviteSuccess"),
    inviteError404: t("users.inviteError404"),
    inviteErrorGeneric: t("users.inviteErrorGeneric"),
    actionChangeRole: t("users.actionChangeRole"),
    actionRemove: t("users.actionRemove"),
    actionYou: t("users.actionYou"),
    confirmRemove: t("users.confirmRemove"),
    removeSuccess: t("users.removeSuccess"),
    removeError: t("users.removeError"),
    roleChangeSuccess: t("users.roleChangeSuccess"),
    roleChangeError: t("users.roleChangeError"),
    readOnlyNotice: t("users.readOnlyNotice"),
  };

  return (
    <div className="p-6 max-w-[900px] mx-auto">
      <Breadcrumb
        items={[
          { label: getText(locale, "nav.admin"), href: "/admin/analytics" },
          { label: t("users.breadcrumb") },
        ]}
      />
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-extrabold text-foreground m-0">
          {t("users.title")}
        </h1>
        <span className="py-1 px-3 rounded-lg bg-accent text-muted-foreground text-xs font-semibold">
          {t("users.yourRole")}: {role}
        </span>
      </div>
      <UsersTable
        users={rows}
        role={role}
        currentUserEmail={user?.email ?? null}
        locale={locale}
        i18n={i18n}
      />
      <p className="text-xs text-muted-foreground mt-4">
        {t("users.createHint")}
      </p>
    </div>
  );
}
