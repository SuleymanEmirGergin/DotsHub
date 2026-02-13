/**
 * Build HTML for result summary and share as PDF via expo-print + expo-sharing.
 * Falls back to text share on web or if PDF fails.
 */

export type SummaryData = {
  title?: string;
  specialty?: string;
  urgency?: string;
  rationale?: string[];
  candidates?: { label: string; probability?: number }[];
  emergencyWatchouts?: string[];
  summaryLines?: string[];
  disclaimer: string;
};

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function buildSummaryHtml(data: SummaryData): string {
  const parts: string[] = [
    "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
    "body{font-family:system-ui,sans-serif;padding:20px;color:#111;max-width:600px;margin:0 auto;}",
    "h1{font-size:18px;border-bottom:2px solid #333;padding-bottom:8px;}",
    "h2{font-size:14px;margin-top:16px;color:#333;}",
    "p,li{font-size:14px;line-height:1.5;}",
    ".muted{font-size:12px;color:#666;margin-top:24px;}",
    "</style></head><body>",
    "<h1>" + escapeHtml(data.title ?? "Ön-Triyaj Sonuç Özeti") + "</h1>",
  ];
  if (data.specialty) {
    parts.push("<p><strong>Önerilen branş:</strong> " + escapeHtml(data.specialty) + "</p>");
    if (data.urgency) parts.push("<p><strong>Aciliyet:</strong> " + escapeHtml(data.urgency) + "</p>");
  }
  if (data.rationale?.length) {
    parts.push("<h2>Gerekçe</h2><ul>");
    data.rationale.forEach((r) => parts.push("<li>" + escapeHtml(r) + "</li>"));
    parts.push("</ul>");
  }
  if (data.candidates?.length) {
    parts.push("<h2>Olası durumlar</h2><ul>");
    data.candidates.forEach(
      (c) =>
        parts.push(
          "<li>" +
            escapeHtml(c.label) +
            (c.probability != null ? " (%" + Math.round(c.probability * 100) + ")" : "") +
            "</li>"
        )
    );
    parts.push("</ul>");
  }
  if (data.emergencyWatchouts?.length) {
    parts.push("<h2>Acil uyarılar</h2><ul>");
    data.emergencyWatchouts.forEach((w) => parts.push("<li>" + escapeHtml(w) + "</li>"));
    parts.push("</ul>");
  }
  if (data.summaryLines?.length) {
    parts.push("<h2>Doktora gösterilecek özet</h2><ul>");
    data.summaryLines.forEach((l) => parts.push("<li>" + escapeHtml(l) + "</li>"));
    parts.push("</ul>");
  }
  parts.push("<p class='muted'>" + escapeHtml(data.disclaimer) + "</p>");
  parts.push("</body></html>");
  return parts.join("");
}

export async function shareSummaryAsPdf(
  html: string,
  fallbackTextShare?: () => Promise<void>
): Promise<boolean> {
  try {
    const Print = await import("expo-print");
    const Sharing = await import("expo-sharing");
    const isAvailable = await Sharing.isAvailableAsync();
    if (!isAvailable && fallbackTextShare) {
      await fallbackTextShare();
      return false;
    }
    const { uri } = await Print.printToFileAsync({
      html,
      base64: false,
    });
    await Sharing.shareAsync(uri, {
      mimeType: "application/pdf",
      dialogTitle: "Ön-Triyaj Sonuç Özeti",
    });
    return true;
  } catch {
    if (fallbackTextShare) await fallbackTextShare();
    return false;
  }
}
