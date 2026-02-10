"""Admin API endpoints for session management and analytics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.db import supabase
from app.core.config import settings

ADMIN_API_KEY = settings.ADMIN_API_KEY

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_key: Optional[str]) -> None:
    if not ADMIN_API_KEY:
        raise RuntimeError("ADMIN_API_KEY missing")
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")


HEALTH_THRESH_PATH = Path(__file__).resolve().parents[2] / "config" / "admin_health_thresholds.json"


def _load_health_thresholds() -> Dict[str, Any]:
    try:
        return json.loads(HEALTH_THRESH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "low_conf_rate": {"warn": 0.25, "crit": 0.40},
            "high_risk_rate": {"warn": 0.08, "crit": 0.15},
            "min_samples": 80,
        }


def _extract_risk_level(row: Dict[str, Any]) -> str:
    meta = row.get("meta")
    if not isinstance(meta, dict):
        return "NULL"

    rl = meta.get("risk_level")
    if isinstance(rl, str) and rl:
        return rl.upper()

    risk = meta.get("risk")
    if isinstance(risk, dict):
        level = risk.get("level")
        if isinstance(level, str) and level:
            return level.upper()

    return "NULL"


def _extract_risk_score(row: Dict[str, Any]) -> float:
    meta = row.get("meta")
    if not isinstance(meta, dict):
        return 0.0

    rs = meta.get("risk_score_0_1")
    if isinstance(rs, (int, float)):
        return float(rs)

    risk = meta.get("risk")
    if isinstance(risk, dict):
        inner = risk.get("score_0_1")
        if isinstance(inner, (int, float)):
            return float(inner)

    return 0.0


def _is_problem_row(r: Dict[str, Any]) -> bool:
    et = (r.get("envelope_type") or "")
    c = r.get("confidence_0_1")
    c = float(c) if c is not None else 0.0
    rl = _extract_risk_level(r)
    sr = r.get("stop_reason") or ""

    if et == "EMERGENCY":
        return True
    if rl == "HIGH":
        return True
    if et == "RESULT" and c < 0.55:
        return True
    if sr in ("question_budget_exceeded", "min_expected_gain"):
        return True
    return False


@router.get("/sessions")
def list_sessions(
    x_admin_key: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    only_problems: int = Query(default=0, ge=0, le=1),
    envelope_type: Optional[str] = None,
    stop_reason: Optional[str] = None,
):
    require_admin(x_admin_key)

    fetch_n = max(limit * 6, 200)

    q = supabase.table("triage_sessions").select(
        "session_id,created_at,updated_at,envelope_type,stop_reason,confidence_0_1,recommended_specialty_id,extracted_canonicals,meta"
    )

    if envelope_type:
        q = q.eq("envelope_type", envelope_type)

    if stop_reason:
        q = q.eq("stop_reason", stop_reason)

    rows = q.order("created_at", desc=True).limit(fetch_n).execute().data or []

    def sev_rank(r: Dict[str, Any]):
        et = (r.get("envelope_type") or "")
        c = r.get("confidence_0_1")
        c = float(c) if c is not None else 0.0

        rl = _extract_risk_level(r)
        rs = _extract_risk_score(r)

        if et == "EMERGENCY":
            return (0, 0)
        if rl == "HIGH":
            return (1, -rs)
        if et == "RESULT" and c < 0.35:
            return (2, c)
        if et == "RESULT" and c < 0.55:
            return (3, c)
        if et == "QUESTION":
            return (4, 0)
        return (5, 0)

    rows.sort(key=sev_rank)

    if only_problems == 1:
        rows = [r for r in rows if _is_problem_row(r)]

    return {"items": rows[:limit]}


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, x_admin_key: Optional[str] = Header(default=None)):
    require_admin(x_admin_key)

    sess = supabase.table("triage_sessions").select("*").eq("session_id", session_id).single().execute()
    events = (
        supabase.table("triage_events")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    fb = (
        supabase.table("triage_feedback")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )

    return {
        "session": sess.data,
        "events": events.data,
        "feedback": fb.data,
    }


@router.get("/stats/overview")
def overview_stats(
    x_admin_key: Optional[str] = Header(default=None),
    lookback_limit: int = Query(default=800, ge=50, le=5000),
):
    require_admin(x_admin_key)

    rows = (
        supabase.table("triage_sessions")
        .select("session_id,created_at,envelope_type,stop_reason,confidence_0_1,meta,extracted_canonicals")
        .order("created_at", desc=True)
        .limit(lookback_limit)
        .execute()
        .data
        or []
    )

    total = len(rows)
    by_env: Dict[str, int] = {}
    by_stop: Dict[str, int] = {}
    by_risk: Dict[str, int] = {}
    canonical_counts: Dict[str, int] = {}
    low_conf = 0

    for r in rows:
        et = r.get("envelope_type") or "NULL"
        sr = r.get("stop_reason") or "NULL"
        rl = _extract_risk_level(r)

        by_env[et] = by_env.get(et, 0) + 1
        by_stop[sr] = by_stop.get(sr, 0) + 1
        by_risk[rl] = by_risk.get(rl, 0) + 1

        c = r.get("confidence_0_1")
        if c is not None and float(c) < 0.55:
            low_conf += 1

        canonicals = r.get("extracted_canonicals") or []
        for item in canonicals:
            if not item:
                continue
            key = str(item)
            canonical_counts[key] = canonical_counts.get(key, 0) + 1

    top_stop = sorted(by_stop.items(), key=lambda kv: kv[1], reverse=True)[:3]
    top_can = sorted(canonical_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]

    thr = _load_health_thresholds()
    min_samples = int(thr.get("min_samples", 80))

    high = by_risk.get("HIGH", 0)
    high_rate = (high / total) if total else 0.0
    low_rate = (low_conf / total) if total else 0.0

    def judge(val: float, band: Dict[str, Any]) -> str:
        if val >= float(band.get("crit", 1.0)):
            return "CRIT"
        if val >= float(band.get("warn", 1.0)):
            return "WARN"
        return "OK"

    if total < min_samples:
        overall = "INFO"
        low_status = "INFO"
        high_status = "INFO"
    else:
        low_status = judge(low_rate, thr.get("low_conf_rate", {}))
        high_status = judge(high_rate, thr.get("high_risk_rate", {}))
        order = {"OK": 0, "WARN": 1, "CRIT": 2}
        overall = max([low_status, high_status], key=lambda s: order.get(s, 0))

    health = {
        "overall": overall,
        "samples": total,
        "low_conf_rate": low_rate,
        "high_risk_rate": high_rate,
        "low_conf_status": low_status,
        "high_risk_status": high_status,
        "thresholds": thr,
    }

    recent: List[Dict[str, Any]] = []
    for r in rows:
        if not _is_problem_row(r):
            continue
        recent.append(
            {
                "session_id": r.get("session_id"),
                "created_at": r.get("created_at"),
                "envelope_type": r.get("envelope_type"),
                "stop_reason": r.get("stop_reason"),
                "confidence_0_1": r.get("confidence_0_1"),
                "risk_level": (_extract_risk_level(r) or "").upper() or None,
            }
        )
        if len(recent) >= 5:
            break

    return {
        "total": total,
        "by_envelope_type": by_env,
        "by_stop_reason": by_stop,
        "by_risk_level": by_risk,
        "low_confidence_count": low_conf,
        "low_confidence_rate": low_rate,
        "top_stop_reasons": top_stop,
        "top_canonicals": top_can,
        "recent_problem_sessions": recent,
        "health": health,
    }


@router.get("/stats/low_conf_series")
def low_conf_series(
    x_admin_key: Optional[str] = Header(default=None),
    lookback_limit: int = Query(default=800, ge=200, le=10000),
    buckets: int = Query(default=24, ge=8, le=80),
    threshold: float = Query(default=0.55, ge=0.0, le=1.0),
):
    require_admin(x_admin_key)

    rows = (
        supabase.table("triage_sessions")
        .select("created_at,confidence_0_1,envelope_type")
        .order("created_at", desc=True)
        .limit(lookback_limit)
        .execute()
        .data
        or []
    )

    rows = list(reversed(rows))
    if not rows:
        return {"points": []}

    n = len(rows)
    b = min(buckets, n)
    size = max(1, n // b)

    pts = []
    for i in range(0, n, size):
        chunk = rows[i : i + size]
        if not chunk:
            continue

        low = 0
        total = 0
        for r in chunk:
            c = r.get("confidence_0_1")
            if c is None:
                continue
            if r.get("envelope_type") not in ("RESULT", "QUESTION"):
                continue
            total += 1
            if float(c) < threshold:
                low += 1

        rate = (low / total) if total else 0.0
        pts.append({
            "t": chunk[-1].get("created_at"),
            "low_conf_rate": rate,
            "n": total,
        })

    return {"points": pts}


@router.get("/stats/risk_high_series")
def risk_high_series(
    x_admin_key: Optional[str] = Header(default=None),
    lookback_limit: int = Query(default=800, ge=200, le=10000),
    buckets: int = Query(default=24, ge=8, le=80),
):
    require_admin(x_admin_key)

    rows = (
        supabase.table("triage_sessions")
        .select("created_at,meta,envelope_type")
        .order("created_at", desc=True)
        .limit(lookback_limit)
        .execute()
        .data
        or []
    )

    rows = list(reversed(rows))
    if not rows:
        return {"points": []}

    n = len(rows)
    b = min(buckets, n)
    size = max(1, n // b)

    pts = []
    for i in range(0, n, size):
        chunk = rows[i : i + size]
        if not chunk:
            continue

        total = 0
        high = 0
        for r in chunk:
            et = r.get("envelope_type")
            if et not in ("RESULT", "QUESTION", "SAME_DAY"):
                continue
            total += 1
            if _extract_risk_level(r) == "HIGH":
                high += 1

        rate = (high / total) if total else 0.0
        pts.append(
            {
                "t": chunk[-1].get("created_at"),
                "high_risk_rate": rate,
                "n": total,
            }
        )

    return {"points": pts}
