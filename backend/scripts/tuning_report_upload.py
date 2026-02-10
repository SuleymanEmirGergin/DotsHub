"""Tuning report generator + Supabase Storage uploader.

Produces the same analytics as tuning_report.py, plus:
  - Synonym suggestions (from down-feedback sessions)
  - Uploads the JSON to Supabase Storage "reports" bucket

Usage:
  REPORT_DAYS=7 python scripts/tuning_report_upload.py
"""

from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psycopg
from supabase import create_client
from dotenv import load_dotenv

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.synonym_suggest import suggest_synonyms_from_down_sessions, map_token_to_canonical

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


def default_serializer(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def build_report(days: int) -> Dict[str, Any]:
    db_url = os.environ["SUPABASE_DB_URL"]
    since = utc_now() - timedelta(days=days)

    report: Dict[str, Any] = {
        "version": "0.2.0",
        "generated_at": utc_now().isoformat(),
        "window_days": days,
        "since": since.isoformat(),
    }

    with psycopg.connect(db_url) as conn:
        # 1) Down feedback examples (top 50)
        report["down_examples"] = fetchall(conn, """
            SELECT
              s.id AS session_id, s.created_at, s.input_text,
              s.recommended_specialty_id, s.recommended_specialty_tr,
              s.confidence_0_1, s.confidence_label_tr, s.stop_reason,
              s.top_conditions, s.user_canonicals_tr, f.comment
            FROM triage_feedback f
            JOIN triage_sessions s ON s.id = f.session_id
            WHERE f.rating = 'down' AND s.created_at >= %s
            ORDER BY s.created_at DESC LIMIT 50;
        """, (since,))

        # 2) Stop reason breakdown
        report["stop_reason_breakdown"] = fetchall(conn, """
            SELECT COALESCE(stop_reason, 'NULL') AS stop_reason,
                   COUNT(*) AS cnt, AVG(COALESCE(confidence_0_1, 0)) AS avg_conf
            FROM triage_sessions
            WHERE created_at >= %s AND envelope_type IN ('RESULT', 'EMERGENCY')
            GROUP BY 1 ORDER BY cnt DESC;
        """, (since,))

        # 3) Feedback counts
        report["feedback_counts"] = fetchall(conn, """
            SELECT rating, COUNT(*) AS cnt
            FROM triage_feedback WHERE created_at >= %s
            GROUP BY rating ORDER BY cnt DESC;
        """, (since,))

        # 4) Specialty down rate
        report["specialty_down_rate"] = fetchall(conn, """
            WITH base AS (
              SELECT s.recommended_specialty_id AS specialty_id,
                     COUNT(*) FILTER (WHERE f.rating='down') AS down_cnt,
                     COUNT(*) FILTER (WHERE f.rating='up') AS up_cnt
              FROM triage_sessions s
              LEFT JOIN triage_feedback f ON f.session_id = s.id
              WHERE s.created_at >= %s AND s.envelope_type = 'RESULT'
              GROUP BY 1
            )
            SELECT specialty_id, down_cnt, up_cnt,
                   CASE WHEN (down_cnt+up_cnt)=0 THEN 0
                        ELSE ROUND((down_cnt::numeric/(down_cnt+up_cnt))*100, 2)
                   END AS down_rate_pct
            FROM base ORDER BY down_rate_pct DESC, down_cnt DESC;
        """, (since,))

        # 5) Most asked canonicals
        report["most_asked_canonicals"] = fetchall(conn, """
            SELECT canonical, COUNT(*) AS cnt FROM (
              SELECT jsonb_array_elements_text(asked_canonicals) AS canonical
              FROM triage_sessions WHERE created_at >= %s
            ) t GROUP BY canonical ORDER BY cnt DESC LIMIT 50;
        """, (since,))

        # 6) Confidence distribution
        report["confidence_distribution"] = fetchall(conn, """
            SELECT confidence_label_tr, COUNT(*) AS cnt,
                   AVG(COALESCE(confidence_0_1, 0)) AS avg_conf
            FROM triage_sessions
            WHERE created_at >= %s AND envelope_type='RESULT'
            GROUP BY 1 ORDER BY cnt DESC;
        """, (since,))

        # 7) Low-confidence raw text samples
        report["raw_text_samples"] = fetchall(conn, """
            SELECT id AS session_id, created_at, input_text
            FROM triage_sessions
            WHERE created_at >= %s AND envelope_type='RESULT'
              AND (confidence_0_1 IS NULL OR confidence_0_1 < 0.45)
            ORDER BY created_at DESC LIMIT 50;
        """, (since,))

    # 8) Synonym suggestions (from down examples)
    suggestions = suggest_synonyms_from_down_sessions(
        report["down_examples"], min_count=2
    )
    # Map each token to best canonical
    for s in suggestions:
        s["suggested_canonical"] = map_token_to_canonical(
            s["token"], report["down_examples"]
        )
    report["synonym_suggestions"] = [
        s for s in suggestions if s.get("suggested_canonical")
    ]

    return report


def upload_report(report: Dict[str, Any]) -> str:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(url, key)

    name = f"tuning_report_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    content = json.dumps(report, ensure_ascii=False, indent=2, default=default_serializer)
    content_bytes = content.encode("utf-8")

    sb.storage.from_("reports").upload(
        path=name,
        file=content_bytes,
        file_options={"content-type": "application/json", "upsert": "false"},
    )

    return name


def main() -> None:
    days = int(os.environ.get("REPORT_DAYS", "7"))
    report = build_report(days)

    # Also save locally
    Path("reports").mkdir(parents=True, exist_ok=True)
    local_path = Path("reports") / f"tuning_report_{utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    local_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=default_serializer),
        encoding="utf-8",
    )
    print(f"Local: {local_path}")

    # Upload to Supabase Storage
    try:
        name = upload_report(report)
        print(f"Uploaded: {name}")
    except Exception as e:
        print(f"Upload failed: {e} (local file still saved)")


if __name__ == "__main__":
    main()
