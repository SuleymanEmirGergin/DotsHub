#!/usr/bin/env python3
"""Measure deployment impact by comparing before/after metrics.

Calculates impact metrics around deployment time:
  - Down-rate (bad recommendations)
  - Average confidence
  - Average questions per session
  - Daily time-series for sparklines

Usage:
    python scripts/measure_deployment_impact.py [--deployment-id ID]
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_db_connection():
    """Get database connection."""
    import psycopg
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("Missing SUPABASE_DB_URL")
    return psycopg.connect(db_url)


def get_latest_deployment(conn):
    """Get the most recent deployment."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, created_at, title
            FROM tuning_deployments
            WHERE status != 'rolled_back'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "created_at": row[1], "title": row[2]}


def calculate_metrics(conn, start_time, end_time):
    """Calculate metrics for a time window."""
    with conn.cursor() as cur:
        # Fetch sessions in window
        cur.execute("""
            SELECT 
                s.id,
                s.created_at,
                s.confidence_0_1,
                s.turn_index,
                s.envelope_type,
                f.rating,
                f.user_selected_specialty_id,
                s.recommended_specialty_id
            FROM triage_sessions s
            LEFT JOIN triage_feedback f ON f.session_id = s.id
            WHERE s.created_at >= %s AND s.created_at < %s
              AND s.envelope_type = 'result'
            ORDER BY s.created_at
        """, (start_time, end_time))
        
        rows = cur.fetchall()
    
    total = len(rows)
    if total == 0:
        return {" total": 0, "down_rate": 0, "avg_confidence": 0, "avg_questions": 0, "daily_series": []}
    
    # Calculate metrics
    down_count = 0
    confidence_sum = 0
    questions_sum = 0
    
    for row in rows:
        conf = row[2] or 0
        turns = row[3] or 0
        rating = row[5]
        user_spec = row[6]
        rec_spec = row[7]
        
        confidence_sum += conf
        questions_sum += turns
        
        # Down = thumbs down OR user selected different specialty
        if rating == "down" or (user_spec and user_spec != rec_spec):
            down_count += 1
    
    down_rate = down_count / total
    avg_confidence = confidence_sum / total
    avg_questions = questions_sum / total
    
    # Daily series for sparklines (last 7 days)
    daily_series = []
    for i in range(7):
        day_start = start_time + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        if day_end > end_time:
            day_end = end_time
        
        day_metrics = calculate_metrics(conn, day_start, day_end)
        daily_series.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "down_rate": day_metrics.get("down_rate", 0),
            "confidence": day_metrics.get("avg_confidence", 0),
        })
    
    return {
        "total": total,
        "down_rate": round(down_rate, 4),
        "avg_confidence": round(avg_confidence, 4),
        "avg_questions": round(avg_questions, 2),
        "daily_series": daily_series[:7],  # Cap at 7 days
    }


def main():
    deployment_id = None
    if "--deployment-id" in sys.argv:
        idx = sys.argv.index("--deployment-id")
        deployment_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    
    print("=" * 60)
    print("Deployment Impact Measurement")
    print("=" * 60)
    
    conn = get_db_connection()
    
    # Get deployment
    if deployment_id:
        with conn.cursor() as cur:
            cur.execute("SELECT id, created_at, title FROM tuning_deployments WHERE id = %s", (deployment_id,))
            row = cur.fetchone()
            deployment = {"id": row[0], "created_at": row[1], "title": row[2]} if row else None
    else:
        deployment = get_latest_deployment(conn)
    
    if not deployment:
        print("No deployment found")
        return 1
    
    deploy_time = deployment["created_at"]
    print(f"Deployment: {deployment['id']}")
    print(f"Time: {deploy_time}")
    print(f"Title: {deployment['title']}")
    print()
    
    # Define windows (48 hours before/after)
    window_hours = 48
    before_start = deploy_time - timedelta(hours=window_hours)
    before_end = deploy_time
    after_start = deploy_time
    after_end = deploy_time + timedelta(hours=window_hours)
    
    # Calculate metrics
    print(f"Calculating metrics ({window_hours}h windows)...")
    before_metrics = calculate_metrics(conn, before_start, before_end)
    after_metrics = calculate_metrics(conn, after_start, after_end)
    
    # Print results
    print()
    print("=" * 60)
    print("BEFORE Deployment")
    print("=" * 60)
    print(f"  Sessions: {before_metrics['total']}")
    print(f"  Down-rate: {before_metrics['down_rate']:.2%}")
    print(f"  Avg confidence: {before_metrics['avg_confidence']:.3f}")
    print(f"  Avg questions: {before_metrics['avg_questions']:.1f}")
    print()
    
    print("=" * 60)
    print("AFTER Deployment")
    print("=" * 60)
    print(f"  Sessions: {after_metrics['total']}")
    print(f"  Down-rate: {after_metrics['down_rate']:.2%}")
    print(f"  Avg confidence: {after_metrics['avg_confidence']:.3f}")
    print(f"  Avg questions: {after_metrics['avg_questions']:.1f}")
    print()
    
    # Calculate deltas
    if before_metrics['total'] > 0 and after_metrics['total'] > 0:
        delta_down = after_metrics['down_rate'] - before_metrics['down_rate']
        delta_conf = after_metrics['avg_confidence'] - before_metrics['avg_confidence']
        delta_q = after_metrics['avg_questions'] - before_metrics['avg_questions']
        
        print("=" * 60)
        print("IMPACT (Δ)")
        print("=" * 60)
        print(f"  Down-rate change: {delta_down:+.2%}")
        print(f"  Confidence change: {delta_conf:+.3f}")
        print(f"  Questions change: {delta_q:+.1f}")
        print()
    
    # Save report
    report = {
        "deployment_id": deployment["id"],
        "measured_at": datetime.utcnow().isoformat(),
        "before": before_metrics,
        "after": after_metrics,
    }
    
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"impact_{deployment['id']}.json"
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Report saved: {report_path}")
    
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
