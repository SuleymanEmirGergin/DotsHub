"""Admin API endpoints for session management and analytics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, Query

from app.db import supabase
from app.admin_auth import require_admin_key

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_key: Optional[str]) -> None:
    require_admin_key(x_admin_key)


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


@router.get("/feedback/stats")
def feedback_stats(
    x_admin_key: Optional[str] = Header(default=None),
    days: int = Query(default=30, ge=1, le=90),
):
    """Feedback summary statistics with daily trend."""
    require_admin(x_admin_key)

    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    rows = (
        supabase.table("triage_feedback")
        .select("id,session_id,rating,comment,user_selected_specialty_id,created_at")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(2000)
        .execute()
        .data
        or []
    )

    total = len(rows)
    up = sum(1 for r in rows if r.get("rating") == "up")
    down = sum(1 for r in rows if r.get("rating") == "down")
    satisfaction = round((up / total) * 100, 1) if total else 0.0

    # Daily trend
    daily: Dict[str, Dict[str, int]] = {}
    for r in rows:
        day = (r.get("created_at") or "")[:10]
        if not day:
            continue
        if day not in daily:
            daily[day] = {"up": 0, "down": 0}
        daily[day][r.get("rating", "up")] += 1

    trend = sorted(
        [{"date": d, "up": v["up"], "down": v["down"]} for d, v in daily.items()],
        key=lambda x: x["date"],
    )

    # Top down specialties — join with sessions
    down_session_ids = [r["session_id"] for r in rows if r.get("rating") == "down" and r.get("session_id")]
    spec_counts: Dict[str, int] = {}

    if down_session_ids:
        sessions = (
            supabase.table("triage_sessions")
            .select("id,recommended_specialty_tr")
            .in_("id", list(set(down_session_ids))[:200])
            .execute()
            .data
            or []
        )
        sess_map = {s["id"]: s.get("recommended_specialty_tr", "Unknown") for s in sessions}
        for sid in down_session_ids:
            spec = sess_map.get(sid, "Unknown")
            spec_counts[spec] = spec_counts.get(spec, 0) + 1

    top_down_specialties = sorted(spec_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    # Recent comments
    recent_comments = [
        {
            "session_id": r["session_id"],
            "rating": r["rating"],
            "comment": r.get("comment"),
            "created_at": r.get("created_at"),
        }
        for r in rows
        if r.get("comment")
    ][:10]

    return {
        "total": total,
        "up": up,
        "down": down,
        "satisfaction_pct": satisfaction,
        "trend": trend,
        "top_down_specialties": top_down_specialties,
        "recent_comments": recent_comments,
        "days": days,
    }


@router.get("/feedback/list")
def feedback_list(
    x_admin_key: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    rating: Optional[str] = Query(default=None),
):
    """Paginated feedback list with session info."""
    require_admin(x_admin_key)

    q = (
        supabase.table("triage_feedback")
        .select("id,session_id,rating,comment,user_selected_specialty_id,created_at")
        .order("created_at", desc=True)
    )
    if rating in ("up", "down"):
        q = q.eq("rating", rating)

    rows = q.limit(limit).execute().data or []

    # enrich with session data
    session_ids = list(set(r["session_id"] for r in rows if r.get("session_id")))
    sess_map: Dict[str, Dict[str, Any]] = {}

    if session_ids:
        sessions = (
            supabase.table("triage_sessions")
            .select("id,envelope_type,recommended_specialty_tr,confidence_0_1,created_at")
            .in_("id", session_ids[:200])
            .execute()
            .data
            or []
        )
        for s in sessions:
            sess_map[s["id"]] = s

    items = []
    for r in rows:
        sess = sess_map.get(r.get("session_id", ""), {})
        items.append({
            "id": r.get("id"),
            "session_id": r.get("session_id"),
            "rating": r.get("rating"),
            "comment": r.get("comment"),
            "user_selected_specialty_id": r.get("user_selected_specialty_id"),
            "created_at": r.get("created_at"),
            "session_envelope_type": sess.get("envelope_type"),
            "session_specialty": sess.get("recommended_specialty_tr"),
            "session_confidence": sess.get("confidence_0_1"),
            "session_created_at": sess.get("created_at"),
        })

    return {"items": items, "count": len(items)}


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


@router.get("/webhook/status")
def webhook_status(
    x_admin_key: Optional[str] = Header(default=None),
):
    """Return webhook notification configuration status."""
    require_admin(x_admin_key)

    from app.core.config import settings as cfg

    return {
        "enabled": cfg.WEBHOOK_ENABLED,
        "channels": {
            "slack": bool(cfg.WEBHOOK_SLACK_URL),
            "discord": bool(cfg.WEBHOOK_DISCORD_URL),
        },
    }


@router.get("/live")
def live_sessions(
    x_admin_key: Optional[str] = Header(default=None),
    minutes: int = Query(default=5, ge=1, le=60),
):
    """Return sessions with activity in the last N minutes for live monitoring."""
    require_admin(x_admin_key)

    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

    resp = (
        supabase()
        .table("triage_sessions")
        .select(
            "id,session_id,envelope_type,turn_index,"
            "recommended_specialty_tr,confidence_0_1,confidence_label_tr,"
            "stop_reason,input_text,locale,"
            "created_at,updated_at"
        )
        .gte("updated_at", cutoff)
        .order("updated_at", desc=True)
        .limit(50)
        .execute()
    )

    rows = resp.data or []
    now = datetime.now(timezone.utc)

    items = []
    for r in rows:
        updated = r.get("updated_at", "")
        created = r.get("created_at", "")
        envelope = r.get("envelope_type", "QUESTION")

        # Compute status
        if envelope in ("RESULT", "EMERGENCY"):
            status = "completed"
        elif updated:
            try:
                dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age_sec = (now - dt).total_seconds()
                status = "active" if age_sec < 30 else "waiting"
            except Exception:
                status = "waiting"
        else:
            status = "waiting"

        items.append({
            "id": r.get("session_id") or r.get("id"),
            "envelope_type": envelope,
            "turn_index": r.get("turn_index", 0),
            "specialty": r.get("recommended_specialty_tr"),
            "confidence": r.get("confidence_0_1"),
            "confidence_label": r.get("confidence_label_tr"),
            "stop_reason": r.get("stop_reason"),
            "input_text": (r.get("input_text") or "")[:80],
            "locale": r.get("locale", "tr-TR"),
            "status": status,
            "created_at": created,
            "updated_at": updated,
        })

    return {"items": items, "cutoff_minutes": minutes}


@router.post("/webhook/test")
def webhook_test(
    x_admin_key: Optional[str] = Header(default=None),
):
    """Send a test message to all configured webhook channels."""
    require_admin(x_admin_key)

    from app.notifier import send_test

    results = send_test()
    return {"results": results}


@router.get("/users")
def list_admin_users(
    x_admin_key: Optional[str] = Header(default=None),
):
    """List all admin users."""
    require_admin(x_admin_key)

    resp = (
        supabase()
        .table("admin_users")
        .select("id,user_id,email,role,created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return {"users": resp.data or []}


@router.post("/users")
def add_admin_user(
    x_admin_key: Optional[str] = Header(default=None),
    email: str = Query(...),
    user_id: str = Query(...),
    role: str = Query(default="admin"),
):
    """Add a new admin user."""
    require_admin(x_admin_key)

    resp = (
        supabase()
        .table("admin_users")
        .upsert(
            {"user_id": user_id, "email": email, "role": role},
            on_conflict="user_id",
        )
        .execute()
    )
    return {"ok": True, "data": resp.data}


@router.delete("/users/{user_id}")
def remove_admin_user(
    user_id: str,
    x_admin_key: Optional[str] = Header(default=None),
):
    """Remove an admin user."""
    require_admin(x_admin_key)

    supabase().table("admin_users").delete().eq("user_id", user_id).execute()
    return {"ok": True}


@router.get("/stats/llm")
def llm_stats(
    x_admin_key: Optional[str] = Header(default=None),
    lookback_days: int = Query(default=7, ge=1, le=90),
):
    """LLM NLU call metrics: success rate, latency percentiles, nlu_source breakdown, daily counts."""
    require_admin(x_admin_key)

    from datetime import datetime, timezone, timedelta
    from collections import defaultdict

    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    rows = (
        supabase.table("llm_calls")
        .select("success,error_type,latency_ms,nlu_source,created_at,model,provider")
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(5000)
        .execute()
        .data or []
    )

    total = len(rows)
    success_count = sum(1 for r in rows if r.get("success"))

    # error breakdown
    error_counts: Dict[str, int] = {}
    for r in rows:
        if not r.get("success"):
            et = r.get("error_type") or "unknown"
            error_counts[et] = error_counts.get(et, 0) + 1

    # latency stats (success only)
    latencies = sorted(
        r["latency_ms"] for r in rows
        if r.get("success") and r.get("latency_ms") is not None
    )
    def _pct(lst, p):
        if not lst:
            return 0
        idx = max(0, int(len(lst) * p / 100) - 1)
        return lst[idx]

    avg_latency_ms = round(sum(latencies) / len(latencies)) if latencies else 0

    # nlu_source distribution
    by_nlu_source: Dict[str, int] = {}
    for r in rows:
        src = r.get("nlu_source") or "unknown"
        by_nlu_source[src] = by_nlu_source.get(src, 0) + 1

    # daily call counts
    daily: Dict[str, int] = defaultdict(int)
    for r in rows:
        day = (r.get("created_at") or "")[:10]
        daily[day] += 1

    # model/provider in use
    models = list({r.get("model") for r in rows if r.get("model")})
    providers = list({r.get("provider") for r in rows if r.get("provider")})

    return {
        "lookback_days": lookback_days,
        "total_calls": total,
        "success_count": success_count,
        "success_rate": round(success_count / total, 4) if total else 0.0,
        "error_counts": error_counts,
        "latency_ms": {
            "avg": avg_latency_ms,
            "p50": _pct(latencies, 50),
            "p90": _pct(latencies, 90),
            "p95": _pct(latencies, 95),
            "p99": _pct(latencies, 99),
        },
        "by_nlu_source": by_nlu_source,
        "daily_counts": dict(sorted(daily.items())),
        "models": models,
        "providers": providers,
    }


@router.get("/stats/synonym-suggestions")
def synonym_suggestions(
    x_admin_key: Optional[str] = Header(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[str] = Query(default=None),
    min_count: int = Query(default=2, ge=1),
):
    """Unrecognized symptom phrases from LLM NLU — candidates for new synonym entries.

    Sorted by occurrence count descending. Filter by status: pending | accepted | rejected.
    Only returns phrases seen at least min_count times to reduce noise.
    """
    require_admin(x_admin_key)

    q = (
        supabase.table("synonym_suggestions")
        .select("id,phrase,count,status,suggested_canonical,created_at,updated_at")
        .gte("count", min_count)
        .order("count", desc=True)
    )
    if status:
        q = q.eq("status", status)

    rows = q.limit(limit).execute().data or []
    return {"items": rows, "total": len(rows)}


@router.patch("/stats/synonym-suggestions/{suggestion_id}")
def update_synonym_suggestion(
    suggestion_id: int,
    x_admin_key: Optional[str] = Header(default=None),
    status: str = Query(..., description="pending | accepted | rejected"),
    suggested_canonical: Optional[str] = Query(default=None),
):
    """Update a synonym suggestion's review status.

    - status=accepted  → mark phrase as approved to add to synonyms_tr.json
    - status=rejected  → dismiss the phrase
    - suggested_canonical → the canonical string this phrase should map to
    """
    require_admin(x_admin_key)

    if status not in ("pending", "accepted", "rejected"):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="status must be: pending | accepted | rejected")

    patch: Dict[str, Any] = {"status": status}
    if suggested_canonical is not None:
        patch["suggested_canonical"] = suggested_canonical.strip() or None

    result = (
        supabase.table("synonym_suggestions")
        .update(patch)
        .eq("id", suggestion_id)
        .execute()
    )

    updated = result.data or []
    if not updated:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"synonym_suggestion id={suggestion_id} not found")

    return {"ok": True, "updated": updated[0]}
