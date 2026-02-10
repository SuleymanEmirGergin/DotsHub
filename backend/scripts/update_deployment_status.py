#!/usr/bin/env python3
"""Update deployment status in database.

Usage:
    python scripts/update_deployment_status.py --deployment-id ID --status STATUS
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def update_status(deployment_id: str, status: str):
    """Update deployment status."""
    from supabase import create_client
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError("Missing Supabase credentials")
    
    sb = create_client(url, key)
    
    valid_statuses = ["applied", "rolled_back_pending", "rolled_back"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}")
    
    res = sb.table("tuning_deployments").update({"status": status}).eq("id", deployment_id).execute()
    
    if not res.data:
        raise ValueError(f"Deployment not found: {deployment_id}")
    
    print(f"✓ Updated deployment {deployment_id} → {status}")


def main():
    if "--deployment-id" not in sys.argv or "--status" not in sys.argv:
        print("Usage: update_deployment_status.py --deployment-id ID --status STATUS")
        return 1
    
    idx_id = sys.argv.index("--deployment-id")
    idx_status = sys.argv.index("--status")
    
    deployment_id = sys.argv[idx_id + 1] if idx_id + 1 < len(sys.argv) else None
    status = sys.argv[idx_status + 1] if idx_status + 1 < len(sys.argv) else None
    
    if not deployment_id or not status:
        print("Error: Missing arguments")
        return 1
    
    try:
        update_status(deployment_id, status)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
