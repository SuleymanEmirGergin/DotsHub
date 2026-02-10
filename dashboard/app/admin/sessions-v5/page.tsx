"use client";

import { useEffect, useMemo, useState } from "react";

type SessionRow = {
  session_id: string;
  created_at: string;
  updated_at: string;
  envelope_type: string | null;
  stop_reason: string | null;
  confidence_0_1: number | null;
  recommended_specialty_id: number | null;
  extracted_canonicals: string[];
  meta: any;
};

type SessionsResp = { items: SessionRow[] };

type HealthStatus = "INFO" | "OK" | "WARN" | "CRIT";

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
    thresholds: any;
  };
};

type SessionDetail = {
  session: any;
  events: any[];
  feedback: any[];
};

function pillClass(kind: HealthStatus) {
  const base = "inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold border";
  if (kind === "CRIT") return `${base} border-red-500 text-red-600`;
  if (kind === "WARN") return `${base} border-amber-500 text-amber-600`;
  if (kind === "OK") return `${base} border-emerald-500 text-emerald-600`;
  return `${base} border-slate-400 text-slate-500`;
}

function riskBadge(level?: string) {
  const base = "inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold border";
  const l = String(level || "").toUpperCase();
  if (l === "HIGH") return `${base} border-red-500 text-red-600`;
  if (l === "MEDIUM") return `${base} border-amber-500 text-amber-600`;
  if (l === "LOW") return `${base} border-emerald-500 text-emerald-600`;
  return `${base} border-slate-300 text-slate-500`;
}

function getRiskLevel(meta: any): string | undefined {
  if (!meta || typeof meta !== "object") return undefined;
  const direct = meta?.risk_level;
  if (typeof direct === "string" && direct) return direct.toUpperCase();
  const nested = meta?.risk?.level;
  if (typeof nested === "string" && nested) return nested.toUpperCase();
  return undefined;
}

function getRiskScore(meta: any): number | undefined {
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

function fmtPct(x: number) {
  return `${Math.round(x * 100)}%`;
}

function Sparkline({ values }: { values: number[] }) {
  const w = 220;
  const h = 44;
  const pad = 4;

  if (!values.length) {
    return <div className="text-xs text-slate-500">-</div>;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-9, max - min);

  const pts = values.map((v, i) => {
    const x = pad + (i * (w - pad * 2)) / Math.max(1, values.length - 1);
    const y = h - pad - ((v - min) / span) * (h - pad * 2);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });

  return (
    <svg width={w} height={h} className="block">
      <polyline fill="none" stroke="currentColor" strokeWidth="2" points={pts.join(" ")} />
    </svg>
  );
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
    const [s, o, lc, rh] = await Promise.all([
      fetch(`/api/admin/sessions?${query}`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`/api/admin/stats?lookback_limit=800`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`/api/admin/lowconf?lookback_limit=800&buckets=28&threshold=0.55`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`/api/admin/riskhigh?lookback_limit=800&buckets=28`, { cache: "no-store" }).then((r) => r.json()),
    ]);

    setItems((s as SessionsResp).items ?? []);
    setOverview(o as Overview);
    setSeries((lc?.points ?? []).map((p: any) => Number(p.low_conf_rate) || 0));
    setRiskHighSeries((rh?.points ?? []).map((p: any) => Number(p.high_risk_rate) || 0));
  }

  useEffect(() => {
    load();
  }, [query]);

  const high = overview?.by_risk_level?.HIGH ?? 0;
  const total = overview?.total ?? 0;
  const highRate = total ? high / total : 0;

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

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="rounded-2xl border p-4">
          <div className="text-xs text-slate-500">Total (lookback)</div>
          <div className="text-2xl font-bold">{overview?.total ?? "-"}</div>
        </div>

        <div className="rounded-2xl border p-4">
          <div className="text-xs text-slate-500 flex items-center justify-between">
            <span>Low confidence rate</span>
            <span className={pillClass((overview?.health?.low_conf_status as HealthStatus) ?? "INFO")}>
              {overview?.health?.low_conf_status ?? "-"}
            </span>
          </div>
          <div className="mt-2 text-slate-600">
            <Sparkline values={series} />
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {overview ? fmtPct(overview.health?.low_conf_rate ?? overview.low_confidence_rate) : "-"}
          </div>

          <div className="mt-3 pt-3 border-t">
            <div className="text-xs text-slate-500 flex items-center justify-between">
              <span>High risk rate</span>
              <span className={pillClass((overview?.health?.high_risk_status as HealthStatus) ?? "INFO")}>
                {overview?.health?.high_risk_status ?? "-"}
              </span>
            </div>
            <div className="mt-2 text-slate-600">
              <Sparkline values={riskHighSeries} />
            </div>
            <div className="text-xs text-slate-500 mt-1">{fmtPct(overview?.health?.high_risk_rate ?? highRate)}</div>
          </div>
        </div>

        <div className="rounded-2xl border p-4">
          <div className="text-xs text-slate-500">By envelope</div>
          <div className="mt-2 space-y-1 text-sm">
            {overview
              ? Object.entries(overview.by_envelope_type)
                  .sort((a, b) => Number(b[1]) - Number(a[1]))
                  .slice(0, 6)
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-slate-600">{k}</span>
                      <span className="font-semibold">{v}</span>
                    </div>
                  ))
              : "-"}
          </div>
        </div>

        <div className="rounded-2xl border p-4">
          <div className="text-xs text-slate-500">By stop reason</div>
          <div className="mt-2 space-y-1 text-sm">
            {overview
              ? Object.entries(overview.by_stop_reason)
                  .sort((a, b) => Number(b[1]) - Number(a[1]))
                  .slice(0, 5)
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-slate-600">{k}</span>
                      <span className="font-semibold">{v}</span>
                    </div>
                  ))
              : "-"}
          </div>

          <div className="mt-3 pt-3 border-t">
            <div className="text-xs text-slate-500">By risk</div>
            <div className="mt-2 space-y-1 text-sm">
              {overview
                ? Object.entries(overview.by_risk_level || {})
                    .sort((a, b) => Number(b[1]) - Number(a[1]))
                    .slice(0, 5)
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between items-center">
                        <span className={riskBadge(k)}>{k}</span>
                        <span className="font-semibold">{v}</span>
                      </div>
                    ))
                : "-"}
            </div>
            <div className="text-xs text-slate-500 mt-1">High risk rate: {Math.round(highRate * 100)}%</div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border p-4 flex flex-wrap gap-3 items-end">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} />
          only problems
        </label>

        <div className="flex flex-col gap-1">
          <div className="text-xs text-slate-500">limit</div>
          <input
            className="rounded-xl border px-3 py-2 text-sm w-28"
            type="number"
            value={limit}
            min={1}
            max={200}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </div>

        <div className="flex flex-col gap-1">
          <div className="text-xs text-slate-500">envelope</div>
          <select className="rounded-xl border px-3 py-2 text-sm" value={envelopeType} onChange={(e) => setEnvelopeType(e.target.value)}>
            <option value="">All</option>
            <option value="QUESTION">QUESTION</option>
            <option value="RESULT">RESULT</option>
            <option value="EMERGENCY">EMERGENCY</option>
            <option value="SAME_DAY">SAME_DAY</option>
          </select>
        </div>

        <div className="flex flex-col gap-1 min-w-[260px]">
          <div className="text-xs text-slate-500">stop_reason</div>
          <input
            className="rounded-xl border px-3 py-2 text-sm"
            placeholder="e.g. min_expected_gain"
            value={stopReason}
            onChange={(e) => setStopReason(e.target.value)}
          />
        </div>

        <button
          className="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50"
          onClick={() => {
            setOnlyProblems(true);
            setLimit(50);
            setEnvelopeType("");
            setStopReason("");
          }}
        >
          Clear
        </button>
      </div>

      <div className="rounded-2xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr className="text-left">
              <th className="p-3">Severity</th>
              <th className="p-3">Session</th>
              <th className="p-3">Envelope</th>
              <th className="p-3">Risk</th>
              <th className="p-3">Confidence</th>
              <th className="p-3">Stop reason</th>
              <th className="p-3">Canonicals</th>
              <th className="p-3">Updated</th>
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

  const session = detail?.session;
  const rl = getRiskLevel(session?.meta);
  const rs = getRiskScore(session?.meta);

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full md:w-[720px] bg-white shadow-xl border-l p-4 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="font-bold">Session {sessionId}</div>
          <button className="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50" onClick={onClose}>
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
