"""Tuning Report Generator — produces JSON analytics from Supabase/Postgres.

Aggregates:
  1. Top "down" feedback examples
  2. stop_reason breakdown
  3. Feedback rating counts
  4. Specialty-level down rate (most critical for tuning)
  5. Most asked canonical questions
  6. Confidence distribution
  7. Low-confidence raw text samples (synonym/mapping gap hints)

Usage:
  python scripts/tuning_report.py --days 7 --out reports
"""

from __future__ import annotations
import argparse
import json
import os
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate tuning report from Supabase DB")
    ap.add_argument("--days", type=int, default=7, help="Lookback window in days")
    ap.add_argument("--out", default="reports", help="Output directory")
    args = ap.parse_args()

    db_url = os.environ["SUPABASE_DB_URL"]
    since = utc_now() - timedelta(days=args.days)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "version": "0.1.0",
        "generated_at": utc_now().isoformat(),
        "window_days": args.days,
        "since": since.isoformat(),
    }

    with psycopg.connect(db_url) as conn:
        # 1) Down feedback examples (top 20)
        report["down_examples"] = fetchall(
            conn,
            """
            SELECT
              s.id AS session_id,
              s.created_at,
              s.input_text,
              s.recommended_specialty_id,
              s.recommended_specialty_tr,
              s.confidence_0_1,
              s.confidence_label_tr,
              s.stop_reason,
              s.top_conditions,
              f.comment
            FROM triage_feedback f
            JOIN triage_sessions s ON s.id = f.session_id
            WHERE f.rating = 'down'
              AND s.created_at >= %s
            ORDER BY s.created_at DESC
            LIMIT 20;
            """,
            (since,),
        )

        # 2) stop_reason breakdown
        report["stop_reason_breakdown"] = fetchall(
            conn,
            """
            SELECT
              COALESCE(stop_reason, 'NULL') AS stop_reason,
              COUNT(*) AS cnt,
              AVG(COALESCE(confidence_0_1, 0)) AS avg_conf
            FROM triage_sessions
            WHERE created_at >= %s
              AND envelope_type IN ('RESULT', 'EMERGENCY')
            GROUP BY 1
            ORDER BY cnt DESC;
            """,
            (since,),
        )

        # 3) Feedback rating counts
        report["feedback_counts"] = fetchall(
            conn,
            """
            SELECT rating, COUNT(*) AS cnt
            FROM triage_feedback
            WHERE created_at >= %s
            GROUP BY rating
            ORDER BY cnt DESC;
            """,
            (since,),
        )

        # 4) Specialty-level down rate (most critical tuning list)
        report["specialty_down_rate"] = fetchall(
            conn,
            """
            WITH base AS (
              SELECT
                s.recommended_specialty_id AS specialty_id,
                COUNT(*) FILTER (WHERE f.rating = 'down') AS down_cnt,
                COUNT(*) FILTER (WHERE f.rating = 'up')   AS up_cnt
              FROM triage_sessions s
              LEFT JOIN triage_feedback f ON f.session_id = s.id
              WHERE s.created_at >= %s
                AND s.envelope_type = 'RESULT'
              GROUP BY 1
            )
            SELECT
              specialty_id,
              down_cnt,
              up_cnt,
              CASE WHEN (down_cnt + up_cnt) = 0 THEN 0
                   ELSE ROUND((down_cnt::numeric / (down_cnt + up_cnt)) * 100, 2)
              END AS down_rate_pct
            FROM base
            ORDER BY down_rate_pct DESC, down_cnt DESC;
            """,
            (since,),
        )

        # 5) Most asked canonical questions (for question bank expansion)
        report["most_asked_canonicals"] = fetchall(
            conn,
            """
            SELECT canonical, COUNT(*) AS cnt
            FROM (
              SELECT jsonb_array_elements_text(asked_canonicals) AS canonical
              FROM triage_sessions
              WHERE created_at >= %s
            ) t
            GROUP BY canonical
            ORDER BY cnt DESC
            LIMIT 30;
            """,
            (since,),
        )

        # 6) Confidence distribution
        report["confidence_distribution"] = fetchall(
            conn,
            """
            SELECT
              confidence_label_tr,
              COUNT(*) AS cnt,
              AVG(COALESCE(confidence_0_1, 0)) AS avg_conf
            FROM triage_sessions
            WHERE created_at >= %s
              AND envelope_type = 'RESULT'
            GROUP BY 1
            ORDER BY cnt DESC;
            """,
            (since,),
        )

        # 7) Low-confidence raw text samples (synonym/mapping gap hints)
        report["raw_text_samples"] = fetchall(
            conn,
            """
            SELECT id AS session_id, created_at, input_text
            FROM triage_sessions
            WHERE created_at >= %s
              AND envelope_type = 'RESULT'
              AND (confidence_0_1 IS NULL OR confidence_0_1 < 0.45)
            ORDER BY created_at DESC
            LIMIT 50;
            """,
            (since,),
        )

    # ─── Serialize (handle datetime/Decimal) ───
    def default_serializer(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        from decimal import Decimal

        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    out_path = out_dir / f"tuning_report_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=default_serializer),
        encoding="utf-8",
    )
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
