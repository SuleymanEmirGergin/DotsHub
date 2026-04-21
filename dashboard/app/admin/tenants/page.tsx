import { requireAdmin } from "@/lib/requireAdmin";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { CreateTenantForm } from "./CreateTenantForm";

export const dynamic = "force-dynamic";

type TenantEntry = {
  tenant_id: string;
  path: string;
  condition_count: number;
  tenant_scope?: string | null;
  disclaimer_tr?: string | null;
};

async function listTenants(): Promise<{ ok: boolean; tenants: TenantEntry[]; error?: string }> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) {
    return { ok: false, tenants: [], error: "NEXT_PUBLIC_API_BASE veya ADMIN_API_KEY tanımlı değil." };
  }
  try {
    const r = await fetch(`${base.replace(/\/+$/, "")}/v1/admin/tenants`, {
      headers: { "x-admin-key": key },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (!r.ok) return { ok: false, tenants: [], error: `HTTP ${r.status}` };
    const data = await r.json();
    return { ok: true, tenants: data.tenants ?? [] };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "fetch failed";
    return { ok: false, tenants: [], error: msg };
  }
}

export default async function TenantsListPage() {
  await requireAdmin();
  const { ok, tenants, error } = await listTenants();

  return (
    <div className="p-6 max-w-[1200px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb
        items={[
          { label: "Admin", href: "/admin/sessions" },
          { label: "Kiracılar (Tenants)" },
        ]}
      />
      <div className="flex justify-between items-center mt-2">
        <h1 className="text-[26px] font-black m-0">Kiracı Katalogları</h1>
      </div>

      {!ok && (
        <Card className="mt-5 border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30">
          <CardContent className="p-4 text-sm text-red-900 dark:text-red-200">
            <div className="font-semibold mb-1">Yüklenemedi</div>
            <div>{error}</div>
          </CardContent>
        </Card>
      )}

      {ok && (
        <>
          <div className="mt-5">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Mevcut kiracılar ({tenants.length})</CardTitle>
              </CardHeader>
              <CardContent>
                {tenants.length === 0 ? (
                  <div className="text-sm text-muted-foreground">Henüz kiracı yok.</div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="text-left border-b border-border">
                      <tr>
                        <th className="p-2">Kiracı ID</th>
                        <th className="p-2">Dosya</th>
                        <th className="p-2">Hastalık sayısı</th>
                        <th className="p-2">Disclaimer (kısa)</th>
                        <th className="p-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {tenants.map((t) => (
                        <tr key={t.tenant_id} className="border-b border-border">
                          <td className="p-2 font-mono">{t.tenant_id}</td>
                          <td className="p-2 text-muted-foreground">{t.path}</td>
                          <td className="p-2 font-bold">{t.condition_count}</td>
                          <td className="p-2 text-muted-foreground max-w-[360px] truncate">
                            {t.disclaimer_tr ?? "—"}
                          </td>
                          <td className="p-2 text-right">
                            <Button asChild size="sm" variant="secondary">
                              <Link href={`/admin/tenants/${t.tenant_id}`}>Düzenle</Link>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="mt-5">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Yeni kiracı oluştur</CardTitle>
              </CardHeader>
              <CardContent>
                <CreateTenantForm />
              </CardContent>
            </Card>
          </div>

          <div className="mt-5 text-xs text-muted-foreground">
            Kiracı dosyaları <code>backend/app/data/curated_conditions.&lt;tenant&gt;.json</code>{" "}
            yolunda saklanır. API: <code>/v1/admin/tenants</code>.
          </div>
        </>
      )}
    </div>
  );
}
