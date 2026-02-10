#!/usr/bin/env python3
"""Export accepted patches to config files for PR creation.

This script runs in CI/CD to:
  1. Fetch all accepted tuning tasks with patches
  2. Apply patches to config files
  3. Generate deployment bundle for rollback
  4. Create deployment record in database

Usage:
    python scripts/export_patches_for_pr.py [--dry-run]
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.patchgen import apply_synonyms_patch_to_file
from app.patchgen_keywords import apply_keywords_patch_to_file


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]):
    """Save JSON file with pretty print."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_supabase_client():
    """Get Supabase admin client."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def fetch_accepted_tasks(sb):
    """Fetch all accepted tuning tasks with patches."""
    res = sb.table("tuning_tasks").select("*").eq("status", "accepted").is_("deployment_id", "null").execute()
    return res.data or []


def group_patches_by_type(tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group patches by type."""
    grouped = {"synonyms": [], "answer_boosts": [], "other": []}
    
    for task in tasks:
        patch = task.get("patch") or {}
        patch_type = patch.get("patch_type", "other")
        if patch_type in grouped:
            grouped[patch_type].append({"task": task, "patch": patch})
        else:
            grouped["other"].append({"task": task, "patch": patch})
    
    return grouped


def apply_patches(grouped: Dict[str, List[Dict[str, Any]]], config_dir: Path, dry_run: bool = False):
    """Apply patches to config files."""
    changes = []
    
    # Apply synonyms patches
    if grouped["synonyms"]:
        syn_path = config_dir / "synonyms_tr.json"
        if not syn_path.exists():
            print(f"Warning: {syn_path} not found, skipping synonyms patches")
        else:
            syn_data = load_json(syn_path)
            original_count = len(syn_data.get("synonyms", []))
            
            for item in grouped["synonyms"]:
                syn_data = apply_synonyms_patch_to_file(item["patch"], syn_data)
            
            new_count = len(syn_data.get("synonyms", []))
            
            if not dry_run:
                save_json(syn_path, syn_data)
            
            changes.append({
                "file": "synonyms_tr.json",
                "patch_count": len(grouped["synonyms"]),
                "original_entries": original_count,
                "new_entries": new_count,
                "task_ids": [item["task"]["id"] for item in grouped["synonyms"]],
            })
    
    # Apply keywords patches
    if grouped["answer_boosts"]:
        kw_path = config_dir / "specialty_keywords_tr.json"
        if not kw_path.exists():
            print(f"Warning: {kw_path} not found, skipping keywords patches")
        else:
            kw_data = load_json(kw_path)
            
            for item in grouped["answer_boosts"]:
                kw_data = apply_keywords_patch_to_file(item["patch"], kw_data)
            
            if not dry_run:
                save_json(kw_path, kw_data)
            
            changes.append({
                "file": "specialty_keywords_tr.json",
                "patch_count": len(grouped["answer_boosts"]),
                "task_ids": [item["task"]["id"] for item in grouped["answer_boosts"]],
            })
    
    return changes


def create_deployment_bundle(changes: List[Dict[str, Any]], config_dir: Path, reports_dir: Path):
    """Create deployment bundle for rollback."""
    bundle_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bundle = {
        "id": bundle_id,
        "created_at": datetime.utcnow().isoformat(),
        "changes": changes,
        "files": {},
    }
    
    # Store original file contents for rollback
    for change in changes:
        file_path = config_dir / change["file"]
        if file_path.exists():
            bundle["files"][change["file"]] = load_json(file_path)
    
    # Save bundle
    bundle_path = reports_dir / f"deploy_bundle_{bundle_id}.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(bundle_path, bundle)
    
    print(f"✓ Deployment bundle created: {bundle_path}")
    return bundle_id, bundle


def create_deployment_record(sb, bundle_id: str, task_ids: List[str], changes: List[Dict[str, Any]]):
    """Create deployment record in database."""
    git_sha = os.environ.get("GITHUB_SHA", "unknown")
    
    # Create deployment
    deployment = {
        "title": f"Tuning deployment {bundle_id}",
        "notes": f"Applied {len(task_ids)} patches: {len(changes)} files modified",
        "git_sha": git_sha,
        "status": "applied",
    }
    
    res = sb.table("tuning_deployments").insert(deployment).execute()
    deployment_id = res.data[0]["id"] if res.data else None
    
    if deployment_id:
        # Link tasks to deployment
        sb.table("tuning_tasks").update({"deployment_id": deployment_id}).in_("id", task_ids).execute()
        print(f"✓ Deployment record created: {deployment_id}")
    
    return deployment_id


def main():
    dry_run = "--dry-run" in sys.argv
    
    print("=" * 60)
    print("Export Patches for PR")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    # Setup
    sb = get_supabase_client()
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "app" / "data"
    reports_dir = project_root / "reports"
    
    # Fetch tasks
    print("Fetching accepted tuning tasks...")
    tasks = fetch_accepted_tasks(sb)
    print(f"Found {len(tasks)} tasks")
    
    if not tasks:
        print("No tasks to process")
        return 0
    
    # Group patches
    grouped = group_patches_by_type(tasks)
    print(f"  Synonyms: {len(grouped['synonyms'])}")
    print(f"  Answer boosts: {len(grouped['answer_boosts'])}")
    print(f"  Other: {len(grouped['other'])}")
    print()
    
    # Apply patches
    print("Applying patches...")
    changes = apply_patches(grouped, config_dir, dry_run=dry_run)
    
    for change in changes:
        print(f"  ✓ {change['file']}: {change['patch_count']} patches")
    print()
    
    if dry_run:
        print("DRY RUN: No files modified, no deployment created")
        return 0
    
    # Create deployment bundle
    all_task_ids = [t["id"] for t in tasks]
    bundle_id, bundle = create_deployment_bundle(changes, config_dir, reports_dir)
    
    # Create deployment record
    deployment_id = create_deployment_record(sb, bundle_id, all_task_ids, changes)
    
    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Tasks processed: {len(tasks)}")
    print(f"Files modified: {len(changes)}")
    print(f"Deployment ID: {deployment_id}")
    print(f"Bundle ID: {bundle_id}")
    print()
    print("Next steps:")
    print("  1. Review modified config files")
    print("  2. Commit changes")
    print("  3. Create PR")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
