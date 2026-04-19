"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function CreateTenantForm() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState("");
  const [disclaimer, setDisclaimer] = useState("");
  const [seedFromDefault, setSeedFromDefault] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await fetch("/api/admin/tenants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: tenantId.trim(),
          disclaimer_tr: disclaimer.trim() || undefined,
          seed_from_default: seedFromDefault,
        }),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data?.detail ?? data?.error ?? `HTTP ${r.status}`);
        return;
      }
      router.refresh();
      router.push(`/admin/tenants/${data.tenant_id}`);
    } catch (e: any) {
      setError(e?.message ?? "istek başarısız");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 max-w-lg">
      <label className="text-sm">
        <div className="text-muted-foreground mb-1">
          Kiracı ID (a-z, 0-9, _, -; en fazla 32 karakter)
        </div>
        <input
          value={tenantId}
          onChange={(e) => setTenantId(e.target.value)}
          placeholder="örn: acibadem_istanbul"
          required
          pattern="[a-z0-9_-]{1,32}"
          className="w-full border border-border rounded px-3 py-2 bg-background"
        />
      </label>

      <label className="text-sm">
        <div className="text-muted-foreground mb-1">
          Disclaimer (opsiyonel — boş bırakılırsa default kullanılır)
        </div>
        <input
          value={disclaimer}
          onChange={(e) => setDisclaimer(e.target.value)}
          placeholder="Bu liste tanı değildir…"
          className="w-full border border-border rounded px-3 py-2 bg-background"
        />
      </label>

      <label className="text-sm flex items-center gap-2">
        <input
          type="checkbox"
          checked={seedFromDefault}
          onChange={(e) => setSeedFromDefault(e.target.checked)}
        />
        <span>Default kataloğu seed olarak kopyala (önerilir)</span>
      </label>

      {error && (
        <div className="text-sm text-red-700 dark:text-red-400">{error}</div>
      )}

      <div>
        <Button type="submit" disabled={busy || !tenantId.trim()}>
          {busy ? "Oluşturuluyor…" : "Kiracı oluştur"}
        </Button>
      </div>
    </form>
  );
}
