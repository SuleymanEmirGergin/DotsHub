"use client";

/**
 * Client-side admin users table.
 *
 * Pure presentational until a super_admin interacts:
 *   • "Kullanıcı davet et" opens an inline invite form (email + role).
 *   • Each row (non-self) exposes a role select + remove button.
 *
 * Why no shadcn Dialog/Select: the rest of this page keeps a minimal
 * plain-Tailwind style; pulling a dialog primitive here just for one
 * modal isn't worth the bundle cost. The invite form lives inline
 * above the table and toggles with a state flag.
 *
 * Self-mutation guard: actions are hidden for the row matching the
 * currently-authenticated user's email. The backend doesn't know the
 * caller's identity (shared x-admin-key auth), so the guard is
 * UI-only — acceptable because the dashboard is the only sanctioned
 * caller path.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";

export type AdminUserRow = {
  id: string;
  user_id: string;
  email: string;
  role: "admin" | "super_admin" | string;
  created_at: string;
};

type Locale = "tr" | "en";

type I18nBag = {
  email: string;
  role: string;
  createdAt: string;
  userId: string;
  noUsers: string;
  noUsersHint: string;
  roleAdmin: string;
  roleSuperAdmin: string;
  inviteButton: string;
  inviteTitle: string;
  inviteDescription: string;
  inviteEmailPlaceholder: string;
  inviteSubmit: string;
  inviteCancel: string;
  inviteRolePrompt: string;
  inviteSuccess: string;
  inviteError404: string;
  inviteErrorGeneric: string;
  actionChangeRole: string;
  actionRemove: string;
  actionYou: string;
  confirmRemove: string;
  removeSuccess: string;
  removeError: string;
  roleChangeSuccess: string;
  roleChangeError: string;
  readOnlyNotice: string;
};

// Minimal {placeholder} → value interpolation. Aligns with the
// hand-rolled formatText in /admin/live/page.tsx so both pages share
// the same expectation for i18n templates.
function formatMsg(template: string, params: Record<string, string>): string {
  let out = template;
  for (const [k, v] of Object.entries(params)) {
    out = out.replaceAll(`{${k}}`, v);
  }
  return out;
}

type Toast =
  | { kind: "success"; text: string }
  | { kind: "error"; text: string };

export default function UsersTable({
  users,
  role,
  currentUserEmail,
  locale,
  i18n,
}: {
  users: AdminUserRow[];
  role: string;
  currentUserEmail: string | null;
  locale: Locale;
  i18n: I18nBag;
}) {
  const router = useRouter();
  const isSuperAdmin = role === "super_admin";

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] =
    useState<"admin" | "super_admin">("admin");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  // Per-row "in-flight" map so we can disable the right row's controls
  // without blocking other rows from being edited concurrently.
  const [rowBusy, setRowBusy] = useState<Record<string, boolean>>({});

  function showToast(t: Toast) {
    setToast(t);
    // Errors stay longer so ops has time to read/copy them.
    const ttl = t.kind === "error" ? 6000 : 3500;
    setTimeout(() => setToast((cur) => (cur === t ? null : cur)), ttl);
  }

  async function submitInvite(e: React.FormEvent) {
    e.preventDefault();
    const email = inviteEmail.trim();
    if (!email || submitting) return;
    setSubmitting(true);
    try {
      const qs = new URLSearchParams({ email, role: inviteRole }).toString();
      const res = await fetch(`/api/admin/users/invite?${qs}`, {
        method: "POST",
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg =
          res.status === 409
            ? i18n.inviteError404
            : formatMsg(i18n.inviteErrorGeneric, {
                msg: body?.detail ?? body?.error ?? `HTTP ${res.status}`,
              });
        showToast({ kind: "error", text: msg });
        return;
      }
      showToast({
        kind: "success",
        text: formatMsg(i18n.inviteSuccess, { email }),
      });
      setInviteEmail("");
      setInviteRole("admin");
      setInviteOpen(false);
      // Refresh server data: router.refresh() re-runs the server page
      // which re-queries admin_users — cleaner than mutating local
      // state and getting out-of-sync with the canonical source.
      router.refresh();
    } catch (err) {
      showToast({
        kind: "error",
        text: formatMsg(i18n.inviteErrorGeneric, {
          msg: err instanceof Error ? err.message : "fetch failed",
        }),
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function changeRole(
    userId: string,
    email: string,
    newRole: "admin" | "super_admin",
  ) {
    setRowBusy((m) => ({ ...m, [userId]: true }));
    try {
      const qs = new URLSearchParams({ role: newRole }).toString();
      const res = await fetch(
        `/api/admin/users/${encodeURIComponent(userId)}?${qs}`,
        { method: "PATCH" },
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        showToast({
          kind: "error",
          text: formatMsg(i18n.roleChangeError, {
            msg: body?.detail ?? `HTTP ${res.status}`,
          }),
        });
        return;
      }
      showToast({
        kind: "success",
        text: formatMsg(i18n.roleChangeSuccess, {
          email,
          role: newRole === "super_admin" ? i18n.roleSuperAdmin : i18n.roleAdmin,
        }),
      });
      router.refresh();
    } catch (err) {
      showToast({
        kind: "error",
        text: formatMsg(i18n.roleChangeError, {
          msg: err instanceof Error ? err.message : "fetch failed",
        }),
      });
    } finally {
      setRowBusy((m) => ({ ...m, [userId]: false }));
    }
  }

  async function removeUser(userId: string, email: string) {
    if (!window.confirm(formatMsg(i18n.confirmRemove, { email }))) return;
    setRowBusy((m) => ({ ...m, [userId]: true }));
    try {
      const res = await fetch(
        `/api/admin/users/${encodeURIComponent(userId)}`,
        { method: "DELETE" },
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        showToast({
          kind: "error",
          text: formatMsg(i18n.removeError, {
            msg: body?.detail ?? `HTTP ${res.status}`,
          }),
        });
        return;
      }
      showToast({
        kind: "success",
        text: formatMsg(i18n.removeSuccess, { email }),
      });
      router.refresh();
    } catch (err) {
      showToast({
        kind: "error",
        text: formatMsg(i18n.removeError, {
          msg: err instanceof Error ? err.message : "fetch failed",
        }),
      });
    } finally {
      setRowBusy((m) => ({ ...m, [userId]: false }));
    }
  }

  const dateLocale = locale === "en" ? "en-US" : "tr-TR";

  return (
    <div>
      {/* Action bar */}
      <div className="flex justify-between items-center gap-3 mb-4 flex-wrap">
        {isSuperAdmin ? (
          <button
            type="button"
            onClick={() => setInviteOpen((v) => !v)}
            className="px-3 py-1.5 text-sm rounded-md border border-primary bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
          >
            {i18n.inviteButton}
          </button>
        ) : (
          <div className="text-xs text-muted-foreground">
            {i18n.readOnlyNotice}
          </div>
        )}
        {toast && (
          <div
            role="status"
            className={
              "text-xs px-3 py-1.5 rounded border " +
              (toast.kind === "success"
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400")
            }
          >
            {toast.text}
          </div>
        )}
      </div>

      {/* Invite form — inline, shown only when super-admin toggles it. */}
      {isSuperAdmin && inviteOpen && (
        <form
          onSubmit={submitInvite}
          className="p-4 mb-4 rounded-xl border border-border bg-card"
        >
          <div className="text-sm font-semibold mb-1">{i18n.inviteTitle}</div>
          <div className="text-xs text-muted-foreground mb-3">
            {i18n.inviteDescription}
          </div>
          <div className="flex gap-2 flex-wrap">
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder={i18n.inviteEmailPlaceholder}
              className="flex-1 min-w-[200px] px-3 py-1.5 text-sm rounded-md border border-border bg-background text-foreground"
              autoFocus
            />
            <label className="sr-only" htmlFor="invite-role">
              {i18n.inviteRolePrompt}
            </label>
            <select
              id="invite-role"
              value={inviteRole}
              onChange={(e) =>
                setInviteRole(e.target.value as "admin" | "super_admin")
              }
              className="px-3 py-1.5 text-sm rounded-md border border-border bg-background text-foreground"
            >
              <option value="admin">{i18n.roleAdmin}</option>
              <option value="super_admin">{i18n.roleSuperAdmin}</option>
            </select>
            <button
              type="submit"
              disabled={submitting || !inviteEmail.trim()}
              className={
                "px-3 py-1.5 text-sm rounded-md border transition-colors " +
                (submitting || !inviteEmail.trim()
                  ? "border-border bg-muted text-muted-foreground cursor-not-allowed"
                  : "border-primary bg-primary text-primary-foreground hover:opacity-90")
              }
            >
              {submitting ? "…" : i18n.inviteSubmit}
            </button>
            <button
              type="button"
              onClick={() => setInviteOpen(false)}
              className="px-3 py-1.5 text-sm rounded-md border border-border bg-card text-muted-foreground hover:bg-muted"
            >
              {i18n.inviteCancel}
            </button>
          </div>
        </form>
      )}

      {/* Users table */}
      <div className="border border-border rounded-2xl overflow-hidden bg-card">
        <table className="w-full border-collapse text-sm text-foreground">
          <thead>
            <tr className="bg-accent text-left">
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                {i18n.email}
              </th>
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                {i18n.role}
              </th>
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                {i18n.createdAt}
              </th>
              <th className="p-3 font-semibold text-xs uppercase tracking-wide text-muted-foreground">
                {i18n.userId}
              </th>
              {isSuperAdmin && <th className="p-3" />}
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && (
              <tr>
                <td
                  colSpan={isSuperAdmin ? 5 : 4}
                  className="p-10 text-center text-muted-foreground"
                >
                  {i18n.noUsers}
                  <br />
                  <span className="text-xs">{i18n.noUsersHint}</span>
                </td>
              </tr>
            )}
            {users.map((u) => {
              const isSelf =
                !!currentUserEmail &&
                !!u.email &&
                u.email.toLowerCase() === currentUserEmail.toLowerCase();
              const busy = !!rowBusy[u.user_id];
              return (
                <tr key={u.id} className="border-t border-border">
                  <td className="p-3.5">
                    <strong>{u.email}</strong>
                    {isSelf && (
                      <span className="ml-2 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wide">
                        {i18n.actionYou}
                      </span>
                    )}
                  </td>
                  <td className="p-3.5">
                    {isSuperAdmin && !isSelf ? (
                      <select
                        value={u.role}
                        onChange={(e) =>
                          changeRole(
                            u.user_id,
                            u.email,
                            e.target.value as "admin" | "super_admin",
                          )
                        }
                        disabled={busy}
                        className="px-2 py-0.5 text-xs rounded-md border border-border bg-background text-foreground disabled:opacity-50"
                        aria-label={i18n.actionChangeRole}
                      >
                        <option value="admin">{i18n.roleAdmin}</option>
                        <option value="super_admin">
                          {i18n.roleSuperAdmin}
                        </option>
                      </select>
                    ) : (
                      <span
                        className={
                          u.role === "super_admin"
                            ? "py-0.5 px-2 rounded-md bg-violet-100 text-violet-600 dark:bg-violet-900/40 dark:text-violet-300 font-semibold text-xs"
                            : "py-0.5 px-2 rounded-md bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300 font-semibold text-xs"
                        }
                      >
                        {u.role === "super_admin"
                          ? i18n.roleSuperAdmin
                          : u.role === "admin"
                            ? i18n.roleAdmin
                            : u.role}
                      </span>
                    )}
                  </td>
                  <td className="p-3.5">
                    {new Date(u.created_at).toLocaleDateString(dateLocale)}
                  </td>
                  <td className="p-3.5 font-mono text-xs">
                    {u.user_id?.slice(0, 8)}…
                  </td>
                  {isSuperAdmin && (
                    <td className="p-3.5 text-right">
                      {!isSelf && (
                        <button
                          type="button"
                          onClick={() => removeUser(u.user_id, u.email)}
                          disabled={busy}
                          className="px-2 py-1 text-xs rounded-md border border-red-500/40 text-red-600 dark:text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                        >
                          {i18n.actionRemove}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
