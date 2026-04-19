"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

type Props = {
  tenantId: string;
  initial: any;
};

// Minimal but complete catalog editor: JSON textarea with a pre-save
// validation pass, a preview of the condition count, and a one-click
// save that calls the Next.js proxy route. No autosave — operators
// want to see what they sent before committing it.
//
// Trade-off: we don't give hospital admins a form-per-field UI (too
// much surface for round 1). A textarea forces them through the JSON
// shape, which is explicit about what the backend will accept.
export function CatalogEditor({ tenantId, initial }: Props) {
  const router = useRouter();
  const initialJson = useMemo(
    () => JSON.stringify(initial ?? {}, null, 2),
    [initial],
  );
  const [text, setText] = useState<string>(initialJson);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<
    | { type: "error" | "success"; msg: string }
    | null
  >(null);

  // Parse preview — gives a condition count and surfaces JSON errors
  // as you type without triggering a save.
  const parsed = useMemo(() => {
    try {
      return { ok: true, data: JSON.parse(text), error: null as null | string };
    } catch (e: any) {
      return { ok: false, data: null, error: String(e?.message ?? e) };
    }
  }, [text]);

  async function onSave() {
    setNotice(null);
    if (!parsed.ok) {
      setNotice({ type: "error", msg: `JSON geçersiz: ${parsed.error}` });
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(
        `/api/admin/tenants/${encodeURIComponent(tenantId)}/curated`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parsed.data),
        },
      );
      const data = await r.json();
      if (!r.ok) {
        setNotice({
          type: "error",
          msg: data?.detail ?? data?.error ?? `HTTP ${r.status}`,
        });
        return;
      }
      setNotice({
        type: "success",
        msg: `Kaydedildi — ${data.condition_count ?? 0} hastalık.`,
      });
    } catch (e: any) {
      setNotice({ type: "error", msg: e?.message ?? "istek başarısız" });
    } finally {
      setBusy(false);
    }
  }

  function onRevert() {
    setText(initialJson);
    setNotice(null);
  }

  async function onDelete() {
    // Two-step confirm — catalog delete is destructive + irreversible
    // from the UI (the audit log preserves the doc, but re-creating
    // the tenant via POST with seed_from_default=false would need
    // that audit row to be replayed by an operator).
    const ok = window.confirm(
      `"${tenantId}" kiracısının tüm kataloğu silinecek. Bu işlem geri alınamaz (audit log'da doc saklanır, oradan restore edilebilir). Devam?`,
    );
    if (!ok) return;
    setBusy(true);
    setNotice(null);
    try {
      const r = await fetch(
        `/api/admin/tenants/${encodeURIComponent(tenantId)}/curated`,
        { method: "DELETE" },
      );
      const data = await r.json();
      if (!r.ok) {
        setNotice({
          type: "error",
          msg: data?.detail ?? data?.error ?? `HTTP ${r.status}`,
        });
        return;
      }
      // After delete, bounce back to the list so the removed tenant
      // doesn't keep rendering in the header breadcrumb.
      router.refresh();
      router.push("/admin/tenants");
    } catch (e: any) {
      setNotice({ type: "error", msg: e?.message ?? "istek başarısız" });
    } finally {
      setBusy(false);
    }
  }

  const conditionCount = parsed.ok
    ? Object.keys(parsed.data?.conditions ?? {}).length
    : null;
  const dirty = text !== initialJson;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div>
          {conditionCount === null ? (
            <span className="text-red-700 dark:text-red-400">JSON geçersiz</span>
          ) : (
            <>
              Hastalık sayısı: <span className="font-bold">{conditionCount}</span>
              {dirty && (
                <span className="ml-3 text-amber-700 dark:text-amber-400">
                  (kaydedilmemiş değişiklikler)
                </span>
              )}
            </>
          )}
        </div>
        <div className="text-[11px]">
          Kiracı: <span className="font-mono">{tenantId}</span>
        </div>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        className="w-full min-h-[520px] font-mono text-[12px] border border-border rounded p-3 bg-muted/40 resize-y"
      />

      {notice && (
        <div
          className={
            notice.type === "error"
              ? "text-sm text-red-700 dark:text-red-400"
              : "text-sm text-emerald-700 dark:text-emerald-400"
          }
        >
          {notice.msg}
        </div>
      )}

      <div className="flex gap-2 items-center">
        <Button onClick={onSave} disabled={busy || !parsed.ok || !dirty}>
          {busy ? "Kaydediliyor…" : "Kaydet"}
        </Button>
        <Button onClick={onRevert} variant="secondary" disabled={busy || !dirty}>
          Değişiklikleri iptal et
        </Button>
        <div className="ml-auto">
          {tenantId !== "default" && (
            <Button
              onClick={onDelete}
              disabled={busy}
              variant="destructive"
              title="Kiracının tüm kataloğunu siler. Audit log'da doc saklanır."
            >
              Kiracıyı sil
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
