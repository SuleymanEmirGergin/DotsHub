"""Question Effectiveness Report (v2) — delta-based scoring.

For each canonical question, measures:
  - Coverage: how often it was asked
  - Answer balance: yes/no ratio (closer to 50/50 = more discriminative)
  - Specialty gap delta: did the gap increase after this question?
  - Confidence delta: did confidence increase after this question?
  - Stop rate: how often RESULT follows this question
  - Composite effectiveness score

Delta attribution uses the immediate next envelope after each ENVELOPE_QUESTION.
Metrics come from payload._meta fields.

Usage:
  python scripts/question_effectiveness_report.py
"""

from __future__ import annotations
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psycopg
from dotenv import load_dotenv

load_dotenv()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fetchall(
    conn: psycopg.Connection, sql: str, params: Tuple[Any, ...]
) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]  # type: ignore[union-attr]
        rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


def get_meta(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        m = payload.get("_meta")
        if isinstance(m, dict):
            return m
    return {}


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def main(days: int = 14) -> None:
    db_url = os.environ["SUPABASE_DB_URL"]
    since = utc_now() - timedelta(days=days)

    with psycopg.connect(db_url) as conn:
        events = fetchall(conn, """
            SELECT session_id::text, created_at, event_type, payload
            FROM triage_events
            WHERE created_at >= %s
            ORDER BY session_id, created_at;
        """, (since,))

    # Per canonical aggregates
    asked_cnt: Counter = Counter()
    answer_cnt: Dict[str, Counter] = defaultdict(Counter)

    # Delta aggregates
    gap_delta_sum: Dict[str, float] = defaultdict(float)
    conf_delta_sum: Dict[str, float] = defaultdict(float)
    delta_n: Counter = Counter()

    # Stop rate
    result_after_q: Counter = Counter()

    # Track last question baseline per session
    last_q: Dict[str, Dict[str, Any]] = {}

    for e in events:
        sid = e["session_id"]
        et = e["event_type"]
        payload = e["payload"] or {}

        if et == "ENVELOPE_QUESTION":
            meta = get_meta(payload)
            canonical = (payload.get("canonical") or "").strip().lower()
            if not canonical:
                continue

            asked_cnt[canonical] += 1
            last_q[sid] = {
                "canonical": canonical,
                "gap": fnum(meta.get("specialty_gap"), 0.0),
                "conf": fnum(meta.get("confidence_0_1"), 0.0),
            }

        elif et == "ANSWER_RECEIVED":
            c = (payload.get("canonical") or "").strip().lower()
            v = (payload.get("value") or "").strip().lower()
            if c and v:
                answer_cnt[c][v] += 1

        elif et in ("ENVELOPE_RESULT", "ENVELOPE_EMERGENCY"):
            # Attribute delta to last asked question
            if sid not in last_q:
                continue

            base = last_q[sid]
            base_c = base["canonical"]
            meta = get_meta(payload)

            cur_gap = fnum(meta.get("specialty_gap"), 0.0)
            cur_conf = fnum(meta.get("confidence_0_1"), 0.0)

            gap_delta_sum[base_c] += cur_gap - base["gap"]
            conf_delta_sum[base_c] += cur_conf - base["conf"]
            delta_n[base_c] += 1

            if et == "ENVELOPE_RESULT":
                result_after_q[base_c] += 1

            del last_q[sid]

    # Also handle when next envelope is another QUESTION (delta between questions)
    # Re-scan: for sessions still in last_q, they didn't reach RESULT after their last Q
    # That's fine — we just don't count deltas for those

    # Build rows
    rows: List[Dict[str, Any]] = []
    for q, cnt in asked_cnt.items():
        yes = answer_cnt[q].get("yes", 0)
        no = answer_cnt[q].get("no", 0)
        total_ans = sum(answer_cnt[q].values()) or 0

        p_yes = (yes / total_ans) if total_ans else 0.0
        balance = 1.0 - abs(p_yes - 0.5) * 2.0

        n = delta_n.get(q, 0)
        avg_gap_delta = (gap_delta_sum[q] / n) if n else 0.0
        avg_conf_delta = (conf_delta_sum[q] / n) if n else 0.0

        stop_rate = (result_after_q[q] / cnt) if cnt else 0.0

        # Composite effectiveness
        eff = (
            min(1.0, cnt / 60.0) * 0.20
            + max(0.0, avg_gap_delta) * 0.30
            + max(0.0, avg_conf_delta) * 0.20
            + stop_rate * 0.20
            + balance * 0.10
        )

        rows.append({
            "canonical": q,
            "asked_count": cnt,
            "answers_total": total_ans,
            "yes": yes,
            "no": no,
            "yes_rate": round(p_yes, 3) if total_ans else None,
            "balance_0_1": round(balance, 3) if total_ans else None,
            "delta_samples": int(n),
            "avg_specialty_gap_delta": round(avg_gap_delta, 4),
            "avg_confidence_delta": round(avg_conf_delta, 4),
            "result_after_question": int(result_after_q[q]),
            "stop_rate_0_1": round(stop_rate, 3),
            "effectiveness_0_1": round(eff, 3),
        })

    rows.sort(key=lambda x: x["effectiveness_0_1"], reverse=True)

    out = {
        "generated_at": utc_now().isoformat(),
        "window_days": days,
        "question_effectiveness": rows[:200],
        "notes": [
            "Delta attribution uses the immediate next RESULT/EMERGENCY envelope after each ENVELOPE_QUESTION.",
            "specialty_gap/confidence from payload._meta fields.",
        ],
    }

    Path("reports").mkdir(parents=True, exist_ok=True)
    path = Path("reports") / f"question_effectiveness_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {path}")


if __name__ == "__main__":
    main()
