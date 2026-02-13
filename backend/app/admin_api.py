"""Admin API router for tuning tasks management.

Provides endpoints for:
  - Creating tuning tasks from sessions
  - Generating patches from tasks
  - Marking tasks as applied
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Any, Dict

from app.tuning_tasks import build_tuning_tasks_from_session
from app.patchgen import build_synonyms_patch_from_task
from app.patchgen_keywords import build_keywords_patch_from_task
from app.admin_auth import require_admin_key

router = APIRouter(prefix="/admin/tuning-tasks", tags=["tuning"])


def require_admin(x_admin_key: str | None = Header(default=None)):
    """Require x-admin-key auth for tuning task admin endpoints."""
    return require_admin_key(x_admin_key)


def get_supabase():
    """Get Supabase admin client."""
    try:
        from supabase import create_client
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not url or not key:
            raise ValueError("Supabase credentials not configured")
        return create_client(url, key)
    except Exception as e:
        raise HTTPException(500, f"Supabase client error: {e}")


@router.post("/from-session/{session_id}")
def create_tasks_from_session(session_id: str, admin=Depends(require_admin)):
    """
    Generate and create tuning tasks from a session.
    
    Analyzes the session and creates deterministic tuning tasks
    for missing keywords, specialty confusion, and weak questions.
    """
    sb = get_supabase()

    # Fetch session
    res = sb.table("triage_sessions").select("*").eq("id", session_id).maybe_single().execute()
    session = res.data
    if not session:
        raise HTTPException(404, "Session not found")

    # Generate tasks
    tasks = build_tuning_tasks_from_session(session)
    if not tasks:
        return {"created": 0, "message": "No tuning tasks generated from this session"}

    # Insert tasks
    created_count = 0
    for t in tasks:
        t["created_by"] = admin.get("user_id")
        try:
            sb.table("tuning_tasks").insert(t).execute()
            created_count += 1
        except Exception as e:
            print(f"Failed to insert task: {e}")
            continue

    return {
        "created": created_count,
        "total": len(tasks),
        "session_id": session_id,
    }


@router.post("/{task_id}/generate-patch")
def generate_patch(task_id: str, admin=Depends(require_admin)):
    """
    Generate and store a patch for a tuning task.
    
    Based on task type, generates appropriate patch:
    - KEYWORD_MISSING → synonyms patch
    - SPECIALTY_CONFUSION → answer_boosts patch
    - QUESTION_WEAKNESS → (future) question adjustment patch
    """
    sb = get_supabase()
    
    # Fetch task
    res = sb.table("tuning_tasks").select("*").eq("id", task_id).maybe_single().execute()
    task = res.data
    if not task:
        raise HTTPException(404, "Task not found")
    
    task_type = task.get("task_type")
    
    # Generate patch based on type
    try:
        if task_type == "KEYWORD_MISSING":
            patch = build_synonyms_patch_from_task(task)
        elif task_type == "SPECIALTY_CONFUSION":
            patch = build_keywords_patch_from_task(task)
        elif task_type == "QUESTION_WEAKNESS":
            # Future: question adjustment logic
            patch = {
                "patch_type": "question_adjustment",
                "changes": [],
                "metadata": {"not_implemented": True}
            }
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    except Exception as e:
        raise HTTPException(400, f"Patch generation failed: {e}")
    
    # Store patch in task
    sb.table("tuning_tasks").update({"patch": patch}).eq("id", task_id).execute()
    
    return {
        "task_id": task_id,
        "patch_type": patch.get("patch_type"),
        "changes_count": len(patch.get("changes", [])),
        "patch": patch,
    }


@router.post("/{task_id}/apply-patch")
def apply_patch(task_id: str, admin=Depends(require_admin)):
    """
    Mark a task's patch as applied (status → accepted).
    
    This signals that the patch has been applied to config files
    (usually via CI/CD automation, not directly here).
    """
    sb = get_supabase()
    
    # Update task status
    res = sb.table("tuning_tasks").update({
        "status": "accepted",
        "applied_at": "now()",
        "applied_by": admin.get("user_id"),
    }).eq("id", task_id).execute()
    
    if not res.data:
        raise HTTPException(404, "Task not found")
    
    return {
        "task_id": task_id,
        "status": "accepted",
        "message": "Patch marked as applied",
    }
