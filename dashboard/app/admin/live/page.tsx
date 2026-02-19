"use client";

import { useEffect, useState, useCallback } from "react";
import { Breadcrumb } from "@/app/components/Breadcrumb";
import { getText } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type LiveSession = {
  id: string;
  envelope_type: string;
  turn_index: number;
  specialty: string | null;
  confidence: number | null;
  confidence_label: string | null;
  stop_reason: string | null;
  input_text: string;
  locale: string;
  status: "active" | "waiting" | "completed";
  created_at: string;
  updated_at: string;
};

const POLL_INTERVAL = 5_000;
const CUTOFF_MINUTES = 10;
const COOKIE_NAME = "NEXT_LOCALE";

function getLocaleFromDocument(): Locale {
  if (typeof document === "undefined") return "tr";
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_NAME}=([^;]*)`));
  return match?.[1] === "en" ? "en" : "tr";
}

function formatText(template: string, params: Record<string, string | number>): string {
  let out = template;
  for (const [key, value] of Object.entries(params)) {
    out = out.replaceAll(`{${key}}`, String(value));
  }
  return out;
}

function timeAgo(iso: string, locale: Locale): string {
  if (!iso) return "";
  const t = (key: string) => getText(locale, key);
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 10) return t("live.justNow");
  if (diff < 60) return `${Math.floor(diff)}${t("live.secondsShort")}`;
  if (diff < 3600) return `${Math.floor(diff / 60)}${t("live.minutesShort")}`;
  return `${Math.floor(diff / 3600)}${t("live.hoursShort")}`;
}

export default function LivePage() {
  const locale = getLocaleFromDocument();
  const t = (key: string) => getText(locale, key);

  const STATUS_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
    active: { bg: "bg-emerald-500/10 text-emerald-500", text: "bg-emerald-500", label: t("live.active") },
    waiting: { bg: "bg-amber-500/10 text-amber-500", text: "bg-amber-500", label: t("live.waiting") },
    completed: { bg: "bg-indigo-500/10 text-indigo-500", text: "bg-indigo-500", label: t("live.completed") },
  };

  const ENVELOPE_CONFIG: Record<string, string> = {
    QUESTION: "bg-blue-500/10 text-blue-500",
    RESULT: "bg-emerald-500/10 text-emerald-400",
    EMERGENCY: "bg-red-500/10 text-red-400",
    SAME_DAY: "bg-amber-500/10 text-amber-400",
  };

  const [sessions, setSessions] = useState<LiveSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [paused, setPaused] = useState(false);
  const [webhookTestResult, setWebhookTestResult] = useState<string | null>(null);
  const [webhookTesting, setWebhookTesting] = useState(false);

  const sendWebhookTest = useCallback(async () => {
    setWebhookTesting(true);
    setWebhookTestResult(null);
    try {
      const res = await fetch("/api/admin/webhook-test", { method: "POST" });
      const data = await res.json();
      const results = data.results || {};
      const msgs: string[] = [];
      if (results.slack) msgs.push(`${t("live.webhookSlack")}: ${results.slack.ok ? "OK" : "FAIL"}`);
      if (results.discord) msgs.push(`${t("live.webhookDiscord")}: ${results.discord.ok ? "OK" : "FAIL"}`);
      setWebhookTestResult(msgs.length > 0 ? msgs.join(" | ") : t("live.webhookUnconfigured"));
    } catch {
      setWebhookTestResult(t("live.connectionError"));
    } finally {
      setWebhookTesting(false);
      setTimeout(() => setWebhookTestResult(null), 4000);
    }
  }, [t]);

  const fetchLive = useCallback(async () => {
    try {
      const res = await fetch(`/api/admin/live?minutes=${CUTOFF_MINUTES}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSessions(data.items || []);
      setLastUpdate(new Date());
      setError(null);
    } catch (err: any) {
      setError(err.message || t("live.connectionError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchLive();
    if (paused) return;
    const id = setInterval(fetchLive, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [fetchLive, paused]);

  const activeSessions = sessions.filter((s) => s.status === "active");
  const waitingSessions = sessions.filter((s) => s.status === "waiting");
  const completedSessions = sessions.filter((s) => s.status === "completed");

  return (
    <div className="p-6 max-w-[1200px] mx-auto">
      <Breadcrumb items={[{ label: getText(locale, "nav.admin"), href: "/admin/analytics" }, { label: t("live.breadcrumb") }]} />
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold text-foreground m-0 flex items-center gap-2.5">
            <span className={cn("w-2.5 h-2.5 rounded-full inline-block", paused ? "bg-gray-500" : "bg-emerald-500 animate-pulse")} />
            {t("live.title")}
          </h1>
          <p className="text-[13px] text-muted-foreground mt-1">
            {formatText(t("live.subtitle"), { minutes: CUTOFF_MINUTES })}
            {lastUpdate && (
              <span> | {t("live.lastUpdate")}: {lastUpdate.toLocaleTimeString(locale === "en" ? "en-US" : "tr-TR")}</span>
            )}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={sendWebhookTest}
            disabled={webhookTesting}
            className="py-2 px-4 rounded-lg border border-border bg-card text-foreground font-semibold text-[13px] cursor-pointer disabled:cursor-wait disabled:opacity-60"
          >
            {webhookTesting ? t("live.sending") : t("live.webhookTest")}
          </button>
          <button
            onClick={() => setPaused((p) => !p)}
            className={cn("py-2 px-4 rounded-lg border border-border font-semibold text-[13px] cursor-pointer", paused ? "bg-primary text-primary-foreground" : "bg-card text-foreground")}
          >
            {paused ? t("live.resume") : t("live.pause")}
          </button>
        </div>
      </div>

      {webhookTestResult && (
        <div className="py-2.5 px-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[13px] font-medium mb-4">
          {webhookTestResult}
        </div>
      )}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3 mb-6">
        <StatCard label={t("live.total")} value={sessions.length} colorClass="text-violet-500" />
        <StatCard label={t("live.active")} value={activeSessions.length} colorClass="text-emerald-500" />
        <StatCard label={t("live.waiting")} value={waitingSessions.length} colorClass="text-amber-500" />
        <StatCard label={t("live.completed")} value={completedSessions.length} colorClass="text-indigo-500" />
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm mb-4 font-medium">
          {error}
        </div>
      )}

      {loading && sessions.length === 0 && (
        <div className="text-center py-14 text-muted-foreground text-sm">{t("live.loading")}</div>
      )}

      {!loading && sessions.length === 0 && !error && (
        <div className="text-center py-14 text-muted-foreground">
          <div className="text-base font-semibold mb-1">{t("live.noActive")}</div>
          <div className="text-[13px]">{formatText(t("live.noRecent"), { minutes: CUTOFF_MINUTES })}</div>
        </div>
      )}

      {sessions.length > 0 && (
        <div className="border border-border rounded-2xl overflow-hidden bg-card">
          <table className="w-full border-collapse text-[13px] text-foreground">
            <thead>
              <tr className="bg-muted/50 text-left">
                <Th>{t("live.status")}</Th>
                <Th>{t("live.session")}</Th>
                <Th>{t("live.type")}</Th>
                <Th>{t("live.step")}</Th>
                <Th>{t("live.specialty")}</Th>
                <Th>{t("live.confidence")}</Th>
                <Th>{t("live.symptom")}</Th>
                <Th>{t("live.updated")}</Th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => {
                const sc = STATUS_CONFIG[s.status] || STATUS_CONFIG.waiting;
                const ec = ENVELOPE_CONFIG[s.envelope_type] ?? "bg-blue-500/10 text-blue-500";
                return (
                  <tr
                    key={s.id}
                    className="border-t border-border transition-colors hover:bg-muted/30"
                  >
                    <td className="p-3">
                      <span className={cn("inline-flex items-center gap-1.5 py-1 px-2.5 rounded-lg font-semibold text-xs", sc.bg)}>
                        <span className={cn("w-1.5 h-1.5 rounded-full", sc.text, s.status === "active" && "animate-pulse")} />
                        {sc.label}
                      </span>
                    </td>
                    <td className="p-3">
                      <a href={`/admin/sessions/${s.id}/replay`} className="text-primary no-underline font-mono text-xs">
                        {s.id.slice(0, 8)}...
                      </a>
                    </td>
                    <td className="p-3">
                      <span className={cn("py-0.5 px-2 rounded-md font-semibold text-[11px] uppercase", ec)}>
                        {s.envelope_type}
                      </span>
                    </td>
                    <td className="p-3 tabular-nums">{s.turn_index}</td>
                    <td className="p-3 max-w-[140px] overflow-hidden text-ellipsis whitespace-nowrap">{s.specialty || "-"}</td>
                    <td className="p-3">
                      {s.confidence != null ? <span className="tabular-nums">{Math.round(s.confidence * 100)}%</span> : "-"}
                    </td>
                    <td className="p-3 max-w-[200px] overflow-hidden text-ellipsis whitespace-nowrap text-muted-foreground text-xs">
                      {s.input_text || "-"}
                    </td>
                    <td className="p-3 text-muted-foreground text-xs">{timeAgo(s.updated_at, locale)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, colorClass }: { label: string; value: number; colorClass: string }) {
  return (
    <div className="p-[18px] rounded-xl border border-border bg-card">
      <div className="text-xs text-muted-foreground font-semibold">{label}</div>
      <div className={cn("text-3xl font-extrabold mt-1 tabular-nums", colorClass)}>{value}</div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="p-3 font-semibold text-[11px] uppercase tracking-wide text-muted-foreground whitespace-nowrap">
      {children}
    </th>
  );
}
