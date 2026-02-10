#!/usr/bin/env python3
"""Guardrail decision script — determines if rollback is needed.

Reads impact metrics and guardrail config to decide on rollback.

Usage:
    python scripts/guardrail_decide.py [--deployment-id ID]
    
Outputs JSON to stdout with decision.
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_config():
    """Load guardrail config."""
    config_path = Path(__file__).parent.parent.parent / "config" / "tuning_guardrails.json"
    if not config_path.exists():
        return {
            "guardrails": {
                "min_feedback_count": 20,
                "thresholds": {
                    "down_rate_increase_max": 0.15,
                    "confidence_decrease_max": 0.10,
                    "avg_questions_increase_max": 1.5,
                }
            }
        }
    
    with open(config_path) as f:
        return json.load(f)


def get_latest_deployment():
    """Get latest deployment ID from Supabase."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    sb = create_client(url, key)
    
    res = sb.table("tuning_deployments").select("id").eq("status", "applied").order("created_at", desc=True).limit(1).execute()
    if res.data:
        return res.data[0]["id"]
    return None


def load_impact_report(deployment_id: str):
    """Load impact report for deployment."""
    report_path = Path(__file__).parent.parent / "reports" / f"impact_{deployment_id}.json"
    if not report_path.exists():
        return None
    
    with open(report_path) as f:
        return json.load(f)


def make_decision(impact: dict, config: dict):
    """Make rollback decision based on impact and thresholds."""
    before = impact.get("before", {})
    after = impact.get("after", {})
    
    min_count = config["guardrails"]["min_feedback_count"]
    thresholds = config["guardrails"]["thresholds"]
    
    # Check if we have enough data
    if after.get("total", 0) < min_count:
        return {
            "should_rollback": False,
            "reason": f"Insufficient data (need {min_count}, got {after.get('total', 0)})",
            "violations": [],
        }
    
    # Calculate deltas
    delta_down = after.get("down_rate", 0) - before.get("down_rate", 0)
    delta_conf = before.get("avg_confidence", 0) - after.get("avg_confidence", 0)  # Note: decrease is bad
    delta_q = after.get("avg_questions", 0) - before.get("avg_questions", 0)
    
    violations = []
    
    # Check thresholds
    if delta_down > thresholds["down_rate_increase_max"]:
        violations.append(f"Down-rate increased by {delta_down:.2%} (max: {thresholds['down_rate_increase_max']:.2%})")
    
    if delta_conf > thresholds["confidence_decrease_max"]:
        violations.append(f"Confidence decreased by {delta_conf:.3f} (max: {thresholds['confidence_decrease_max']:.3f})")
    
    if delta_q > thresholds["avg_questions_increase_max"]:
        violations.append(f"Avg questions increased by {delta_q:.1f} (max: {thresholds['avg_questions_increase_max']:.1f})")
    
    should_rollback = len(violations) > 0
    
    return {
        "should_rollback": should_rollback,
        "reason": "; ".join(violations) if violations else "All checks passed",
        "violations": violations,
        "impact": {
            "delta_down_rate": round(delta_down, 4),
            "delta_confidence": round(delta_conf, 4),
            "delta_questions": round(delta_q, 2),
        }
    }


def main():
    deployment_id = None
    if "--deployment-id" in sys.argv:
        idx = sys.argv.index("--deployment-id")
        deployment_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    
    if not deployment_id:
        deployment_id = get_latest_deployment()
    
    if not deployment_id:
        print(json.dumps({"error": "No deployment found"}))
        return 1
    
    # Load data
    config = load_config()
    impact = load_impact_report(deployment_id)
    
    if not impact:
        print(json.dumps({"error": f"No impact report for deployment {deployment_id}"}))
        return 1
    
    # Make decision
    decision = make_decision(impact, config)
    decision["deployment_id"] = deployment_id
    
    # Output JSON
    print(json.dumps(decision, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
