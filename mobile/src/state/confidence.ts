import type { ResultPayload } from "./types";

export function computeConfidence(result: ResultPayload) {
  const top1 = result.top_conditions?.[0]?.score_0_1 ?? 0;
  const top2 = result.top_conditions?.[1]?.score_0_1 ?? 0;
  const gap = Math.max(0, top1 - top2);

  // Proxy: top1 weighted + gap contribution (deterministic, UI-only)
  const confidence = Math.max(0, Math.min(1, top1 * 0.75 + gap * 0.6));

  let label = "Düşük";
  if (confidence >= 0.7) label = "Yüksek";
  else if (confidence >= 0.45) label = "Orta";

  const hint =
    label === "Yüksek"
      ? "Yönlendirme daha net görünüyor. Yine de doktor değerlendirmesi önerilir."
      : label === "Orta"
        ? "Birkaç olasılık var. Doktora giderken özeti göster."
        : "Belirsizlik yüksek. Semptomlar değişirse veya artarsa değerlendirmeyi yenile.";

  return { confidence, label, hint, gap, top1, top2 };
}
