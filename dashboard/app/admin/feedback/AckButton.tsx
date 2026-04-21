"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Inline "Ack" action per-row on the admin feedback table.
// Small surface on purpose: a 👁 button that opens a prompt for
// the optional note, POSTs to the Next.js proxy, then refreshes
// the page so the row re-renders as acknowledged.
//
// No drawer / modal — the note is optional, the common case is
// "seen, no action needed" which should be one click.
export function AckButton({
  feedbackId,
  acknowledgedAt,
  acknowledgedBy,
  ackNote,
}: {
  feedbackId: string;
  acknowledgedAt: string | null;
  acknowledgedBy: string | null;
  ackNote: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const acked = !!acknowledgedAt;

  async function onAck() {
    const note = window.prompt(
      "Eylem notu (opsiyonel — örn. 'synonym eklendi PR #123')",
      "",
    );
    // null means cancel; empty string means ack without note.
    if (note === null) return;
    setBusy(true);
    try {
      const r = await fetch(
        `/api/admin/feedback/${encodeURIComponent(feedbackId)}/ack`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ack_note: note.trim() || null }),
        },
      );
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        alert(`Acknowledge başarısız: ${data?.detail ?? data?.error ?? r.status}`);
        return;
      }
      router.refresh();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "network";
      alert(`İstek başarısız: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  if (acked) {
    return (
      <div
        className="text-[11px] text-muted-foreground"
        title={
          `Acknowledged: ${new Date(acknowledgedAt!).toLocaleString()}` +
          (acknowledgedBy ? `\nBy: ${acknowledgedBy}` : "") +
          (ackNote ? `\nNote: ${ackNote}` : "")
        }
      >
        ✓ okundu
      </div>
    );
  }

  return (
    <button
      onClick={onAck}
      disabled={busy}
      className="text-[11px] px-2 py-0.5 rounded border border-border bg-muted hover:bg-muted/70 disabled:opacity-50"
      title="Feedback'i okundu olarak işaretle + opsiyonel not bırak"
    >
      {busy ? "…" : "👁 onayla"}
    </button>
  );
}
