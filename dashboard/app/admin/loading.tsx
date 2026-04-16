import { cookies } from "next/headers";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

export default async function AdminLoading() {
  const store = await cookies();
  const locale: Locale = store.get("NEXT_LOCALE")?.value === "en" ? "en" : "tr";
  const loadingLabel = getText(locale, "common.loading");

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 p-6">
      <div
        className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin"
        aria-hidden
      />
      <p className="text-muted-foreground text-sm font-medium">{loadingLabel}</p>
      <div className="flex flex-wrap gap-3 justify-center max-w-md">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-10 w-24 rounded-lg bg-muted/60 animate-pulse"
            aria-hidden
          />
        ))}
      </div>
    </div>
  );
}
