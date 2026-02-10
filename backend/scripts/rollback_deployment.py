#!/usr/bin/env python3
"""Rollback deployment by reverting config files from deployment bundle.

Usage:
    python scripts/rollback_deployment.py --deployment-id ID
"""

import sys
import os
import json
from pathlib import Path


def load_deployment_bundle(deployment_id: str):
    """Load deployment bundle for rollback."""
    reports_dir = Path(__file__).parent.parent / "reports"
    
    # Find bundle file (may have timestamp suffix)
    bundle_files = list(reports_dir.glob(f"deploy_bundle_*{deployment_id}*.json"))
    if not bundle_files:
        # Try exact match
        bundle_path = reports_dir / f"deploy_bundle_{deployment_id}.json"
        if not bundle_path.exists():
            raise FileNotFoundError(f"No deployment bundle found for {deployment_id}")
    else:
        bundle_path = bundle_files[0]
    
    with open(bundle_path) as f:
        return json.load(f)


def revert_files(bundle: dict, config_dir: Path):
    """Revert config files to pre-deployment state."""
    files = bundle.get("files", {})
    
    for filename, original_content in files.items():
        file_path = config_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(original_content, f, indent=2, ensure_ascii=False)
            f.write("\n")
        
        print(f"✓ Reverted: {filename}")


def main():
    if "--deployment-id" not in sys.argv:
        print("Usage: rollback_deployment.py --deployment-id ID")
        return 1
    
    idx = sys.argv.index("--deployment-id")
    deployment_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    
    if not deployment_id:
        print("Error: Missing deployment ID")
        return 1
    
    print("=" * 60)
    print(f"Rolling back deployment: {deployment_id}")
    print("=" * 60)
    
    # Load bundle
    try:
        bundle = load_deployment_bundle(deployment_id)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    
    print(f"Bundle loaded: {bundle.get('id')}")
    print(f"Created at: {bundle.get('created_at')}")
    print(f"Files to revert: {len(bundle.get('files', {}))}")
    print()
    
    # Revert files
    config_dir = Path(__file__).parent.parent / "app" / "data"
    revert_files(bundle, config_dir)
    
    print()
    print("=" * 60)
    print("Rollback complete")
    print("=" * 60)
    print("Next steps:")
    print("  1. Commit reverted files")
    print("  2. Create rollback PR")
    print("  3. Merge to complete rollback")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
