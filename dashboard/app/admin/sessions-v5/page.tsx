"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import SessionsFilter from "./_components/SessionsFilter";
import SessionsStats from "./_components/SessionsStats";
import type { SessionRow, SessionMeta, HealthStatus, SessionDetail } from "@/lib/types/admin";
import { pillClass, riskBadge, fmtPct } from "@/components/ui/health-badge";

type SessionsResp = { items: SessionRow[] };

type Overview = {
  total: number;
  by_envelope_type: Record<string, number>;
  by_stop_reason: Record<string, number>;
  by_risk_level?: Record<string, number>;
  low_confidence_count: number;
  low_confidence_rate: number;
  top_stop_reasons?: Array<[string, number]>;
  top_canonicals?: Array<[string, number]>;
  recent_problem_sessions?: Array<{
    session_id: string;
    created_at: string;
    envelope_type: string;
    stop_reason: string | null;
    confidence_0_1: number | null;
    risk_level: string | null;
  }>;
  health?: {
    overall: HealthStatus;
    samples: number;
    low_conf_rate: number;
    high_risk_rate: number;
    low_conf_status: HealthStatus;
    high_risk_status: HealthStatus;
    thresholds: Record<string, number>;
  };
};

function getRiskLevel(meta: SessionMeta | undefined): string | undefined {
  if (!meta || typeof meta !== "object") return undefined;
  const direct = meta?.risk_level;
  if (typeof direct === "string" && direct) return direct.toUpperCase();
  const nested = meta?.risk?.level;
  if (typeof nested === "string" && nested) return nested.toUpperCase();
  return undefined;
}

function getRiskScore(meta: SessionMeta | undefined): number | undefined {
  if (!meta || typeof meta !== "object") return undefined;
  if (typeof meta?.risk_score_0_1 === "number") return meta.risk_score_0_1;
  if (typeof meta?.risk?.score_0_1 === "number") return meta.risk.score_0_1;
  return undefined;
}

function severityOf(row: SessionRow): HealthStatus {
  const et = row.envelope_type ?? "NULL";
  const c = row.confidence_0_1 ?? 0;
  const rl = getRiskLevel(row?.meta) ?? "";

  if (et === "EMERGENCY") return "CRIT";
  if (rl === "HIGH") return "WARN";
  if (et === "RESULT" && c < 0.35) return "WARN";
  if (et === "RESULT" && c < 0.55) return "INFO";
  if (et === "QUESTION") return "INFO";
  return "OK";
}

function CopyButton({ text }: { text: string }) {
  return (
    <button
      className="rounded-lg border px-2 py-1 text-xs hover:bg-slate-50"
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
      }}
      title="Copy"
    >
      Copy
    </button>
  );
}

function FilterChip({ label, onClick, title }: { label: string; onClick: () => void; title?: string }) {
  return (
    <button
      className="inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold border border-slate-300 text-slate-600 hover:bg-slate-50"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      title={title}
    >
      {label}
    </button>
  );
}

export default function SessionsPageV5() {
  const [items, setItems] = useState<SessionRow[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [series, setSeries] = useState<number[]>([]);
  const [riskHighSeries, setRiskHighSeries] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [onlyProblems, setOnlyProblems] = useState(true);
  const [limit, setLimit] = useState(50);
  const [envelopeType, setEnvelopeType] = useState<string>("");
  const [stopReason, setStopReason] = useState<string>("");

  const [openId, setOpenId] = useState<string | null>(null);

  const query = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    p.set("only_problems", onlyProblems ? "1" : "0");
    if (envelopeType) p.set("envelope_type", envelopeType);
    if (stopReason) p.set("stop_reason", stopReason);
    return p.toString();
  }, [onlyProblems, limit, envelopeType, stopReason]);

  async function load() {
    try {
      setError(null);
      const [s, o, lc, rh] = await Promise.all([
        fetch(`/api/admin/sessions?${query}`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`/api/admin/stats?lookback_limit=800`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`/api/admin/lowconf?lookback_limit=800&buckets=28&threshold=0.55`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`/api/admin/riskhigh?lookback_limit=800&buckets=28`, { cache: "no-store" }).then((r) => r.json()),
      ]);

      setItems((s as SessionsResp).items ?? []);
      setOverview(o as Overview);
      setSeries((lc?.points ?? []).map((p: { low_conf_rate?: unknown }) => Number(p.low_conf_rate) || 0));
      setRiskHighSeries((rh?.points ?? []).map((p: { high_risk_rate?: unknown }) => Number(p.high_risk_rate) || 0));
    } catch {
      setError("Veriler yüklenemedi. Lütfen sayfayı yenileyin.");
    }
  }

  useEffect(() => {
    load();
  }, [query]);

  const high = overview?.by_risk_level?.HIGH ?? 0;
  const total = overview?.total ?? 0;
  const highRate = total ? high / total : 0;

  if (error) {
    return <div className="p-6 text-red-600">{error}</div>;
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">Triage Sessions V5</h1>
            {overview?.health?.overall && (
              <span className={pillClass(overview.health.overall)}>HEALTH {overview.health.overall}</span>
            )}
          </div>
          <p className="text-sm text-slate-500">
            Samples: {overview?.health?.samples ?? "-"} - Envelope-based unified orchestrator.
          </p>
        </div>
        <button className="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50" onClick={load}>
          Refresh
        </button>
      </div>

      <SessionsStats overview={overview} series={series} riskHighSeries={riskHighSeries} />

      <SessionsFilter
        onlyProblems={onlyProblems}
        limit={limit}
        envelopeType={envelopeType}
        stopReason={stopReason}
        onOnlyProblemsChange={setOnlyProblems}
        onLimitChange={setLimit}
        onEnvelopeTypeChange={setEnvelopeType}
        onStopReasonChange={setStopReason}
        onClear={() => {
          setOnlyProblems(true);
          setLimit(50);
          setEnvelopeType("");
          setStopReason("");
        }}
      />

      <div className="rounded-2xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left">
              <th className="p-3" scope="col">Severity</th>
              <th className="p-3" scope="col">Session</th>
              <th className="p-3" scope="col">Envelope</th>
              <th className="p-3" scope="col">Risk</th>
              <th className="p-3" scope="col">Confidence</th>
              <th className="p-3" scope="col">Stop reason</th>
              <th className="p-3" scope="col">Canonicals</th>
              <th className="p-3" scope="col" aria-sort="descending">Updated</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => {
              const sev = severityOf(row);
              const rl = getRiskLevel(row?.meta);
              const rs = getRiskScore(row?.meta);
              return (
                <tr key={row.session_id} className="border-t hover:bg-slate-50 cursor-pointer" onClick={() => setOpenId(row.session_id)}>
                  <td className="p-3">
                    <span className={pillClass(sev)}>{sev}</span>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs">{row.session_id}</span>
                      <CopyButton text={row.session_id} />
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      {row.envelope_type ? (
                        <FilterChip
                          label={row.envelope_type}
                          title="Click to filter by this envelope_type"
                          onClick={() => setEnvelopeType(row.envelope_type ?? "")}
                        />
                      ) : (
                        "-"
                      )}

                      {row?.meta?.same_day ? (
                        <span className="inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold border border-amber-500 text-amber-600">
                          SAME-DAY
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className={riskBadge(rl)}>{rl ?? "-"}</span>
                      {typeof rs === "number" && <span className="text-xs text-slate-500">{Math.round(rs * 100)}%</span>}
                    </div>
                  </td>
                  <td className="p-3">{row.confidence_0_1 == null ? "-" : fmtPct(row.confidence_0_1)}</td>
                  <td className="p-3">
                    {row.stop_reason ? (
                      <FilterChip
                        label={row.stop_reason}
                        title="Click to filter by this stop_reason"
                        onClick={() => setStopReason(row.stop_reason ?? "")}
                      />
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="p-3">
                    <div className="max-w-[360px] truncate text-slate-600">
                      {(row.extracted_canonicals ?? []).slice(0, 6).join(", ") || "-"}
                    </div>
                    {row?.meta?.duration_days ? (
                      <div className="text-xs text-slate-500 mt-1">duration: {row.meta.duration_days}d</div>
                    ) : null}
                  </td>
                  <td className="p-3 text-slate-500">{new Date(row.updated_at).toLocaleString()}</td>
                </tr>
              );
            })}
            {!items.length && (
              <tr>
                <td className="p-6 text-slate-500" colSpan={8}>
                  No sessions.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {openId && <SessionDrawer sessionId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}

function SessionDrawer({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`/api/admin/session/${sessionId}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (alive) setDetail(d as SessionDetail);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [sessionId]);

  // Auto-focus ve Escape key handler
  useEffect(() => {
    const el = drawerRef.current;
    if (!el) return;
    el.focus();

    const drawerEl = el;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const focusable = drawerEl.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const session = detail?.session;
  const rl = getRiskLevel(session?.meta);
  const rs = getRiskScore(session?.meta);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-drawer-title"
      className="fixed inset-0 z-50"
    >
      <div
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onClose(); }}
        role="button"
        aria-label="Kapat"
        tabIndex={0}
      />
      <div ref={drawerRef} tabIndex={-1} className="absolute right-0 top-0 h-full w-full md:w-[720px] shadow-xl border-l p-4 overflow-auto dash-panel">
        <div className="flex items-center justify-between mb-4">
          <div id="session-drawer-title" className="font-bold">Session {sessionId}</div>
          <button aria-label="Kapat" className="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50" onClick={onClose}>
            Close
          </button>
        </div>

        {loading && <div className="text-slate-500 text-sm">Loading...</div>}

        {!loading && (
          <div className="space-y-4">
            {rl && (
              <div className="rounded-2xl border p-4">
                <div className="font-semibold mb-1">Risk</div>
                <div className="flex items-center gap-2">
                  <span className={riskBadge(rl)}>{rl}</span>
                  {typeof rs === "number" && <span className="text-sm text-slate-600">{Math.round(rs * 100)}%</span>}
                  {session?.meta?.duration_days ? (
                    <span className="text-sm text-slate-500">- {session.meta.duration_days}d</span>
                  ) : null}
                </div>
              </div>
            )}

            <div className="rounded-2xl border p-4">
              <div className="font-semibold mb-2">Session</div>
              <pre className="text-xs overflow-auto whitespace-pre-wrap">{JSON.stringify(session ?? {}, null, 2)}</pre>
            </div>

            <div className="rounded-2xl border p-4">
              <div className="font-semibold mb-2">Events ({detail?.events?.length ?? 0})</div>
              <pre className="text-xs overflow-auto whitespace-pre-wrap">{JSON.stringify(detail?.events ?? [], null, 2)}</pre>
            </div>

            <div className="rounded-2xl border p-4">
              <div className="font-semibold mb-2">Feedback ({detail?.feedback?.length ?? 0})</div>
              <pre className="text-xs overflow-auto whitespace-pre-wrap">{JSON.stringify(detail?.feedback ?? [], null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
