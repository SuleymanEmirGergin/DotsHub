import { requireAdmin } from "@/lib/requireAdmin";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { CatalogEditor } from "./CatalogEditor";

export const dynamic = "force-dynamic";

// Shape of the curated catalog JSON we proxy from the backend. Each
// `conditions[disease_label]` entry is an object whose shape varies
// over time (new per-tenant metadata fields land here freely), so
// we keep its value as Record<string, unknown> and let the editor
// handle rendering + validation.
type CatalogPayload = {
  version?: string;
  language?: string;
  disclaimer_tr?: string;
  tenant_scope?: string;
  conditions?: Record<string, Record<string, unknown>>;
};

async function fetchCatalog(id: string): Promise<{ ok: boolean; data?: CatalogPayload; error?: string }> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  const key = process.env.ADMIN_API_KEY;
  if (!base || !key) return { ok: false, error: "NEXT_PUBLIC_API_BASE veya ADMIN_API_KEY tanımlı değil." };
  try {
    const r = await fetch(
      `${base.replace(/\/+$/, "")}/v1/admin/tenants/${encodeURIComponent(id)}/curated`,
      { headers: { "x-admin-key": key }, cache: "no-store", signal: AbortSignal.timeout(10000) },
    );
    if (!r.ok) return { ok: false, error: `HTTP ${r.status}` };
    return { ok: true, data: (await r.json()) as CatalogPayload };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "fetch failed";
    return { ok: false, error: msg };
  }
}

export default async function TenantCatalogPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const { id } = await params;
  const { ok, data, error } = await fetchCatalog(id);

  return (
    <div className="p-6 max-w-[1100px] mx-auto bg-background text-foreground min-h-screen">
      <Breadcrumb
        items={[
          { label: "Admin", href: "/admin/sessions" },
          { label: "Kiracılar", href: "/admin/tenants" },
          { label: id },
        ]}
      />

      <div className="flex justify-between items-center mt-2">
        <h1 className="text-[26px] font-black m-0">
          Kiracı: <span className="font-mono">{id}</span>
        </h1>
        <Button asChild size="sm" variant="secondary">
          <Link href="/admin/tenants">← Listeye dön</Link>
        </Button>
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
        <div className="mt-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Curated catalog ({Object.keys(data?.conditions ?? {}).length} hastalık)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CatalogEditor tenantId={id} initial={data} />
            </CardContent>
          </Card>
        </div>
      )}

      <div className="mt-5 text-xs text-muted-foreground">
        Yapı: <code>{`{ version, language, disclaimer_tr, tenant_scope, conditions: { [disease_label]: { icd10, disease_description_tr, doktora_sorulacak_sorular_tr, izlenecek_belirtiler_tr, ne_zaman_tekrar_basvur_tr, self_care_tr, aciliyet_notu_tr } } }`}</code>.
        Kaydet butonu katalog dosyasını <em>tümüyle</em> yeniden yazar.
      </div>
    </div>
  );
}
