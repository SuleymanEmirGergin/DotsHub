"""Admin API router for tuning tasks management.

Provides endpoints for:
  - Creating tuning tasks from sessions
  - Generating patches from tasks
  - Marking tasks as applied
"""

from __future__ import annotations
import csv
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import PlainTextResponse, Response

from app.tuning_tasks import build_tuning_tasks_from_session
from app.patchgen import build_synonyms_patch_from_task
from app.patchgen_keywords import build_keywords_patch_from_task
from app.admin_auth import require_admin_key
from app.core.config import settings

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
        raise HTTPException(500, f"Supabase client error: {e}") from e


# ─── List & export (tenant-scoped, for dashboard proxy) ───

TUNING_SORT_COLUMNS = ("created_at", "task_type", "title", "status")
VALID_STATUS = ("open", "accepted", "rejected", "done")
VALID_TYPE = ("KEYWORD_MISSING", "SPECIALTY_CONFUSION", "QUESTION_WEAKNESS")


@router.get("")
def list_tuning_tasks(
    admin=Depends(require_admin),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(100, ge=1, le=500),
):
    """List tuning tasks for the current tenant (for dashboard proxy)."""
    sb = get_supabase()
    tenant_id = admin.get("tenant_id") or "default"
    sort_col = sort if sort in TUNING_SORT_COLUMNS else "created_at"
    asc = order.lower() == "asc"

    q = (
        sb.table("tuning_tasks")
        .select("id,created_at,task_type,severity,title,description,status,session_id,patch")
        .eq("tenant_id", tenant_id)
        .order(sort_col, desc=not asc)
        .limit(limit)
    )
    if status and status in VALID_STATUS:
        q = q.eq("status", status)
    if type and type in VALID_TYPE:
        q = q.eq("task_type", type)

    res = q.execute()
    return {"tasks": res.data or []}


@router.get("/export", response_class=PlainTextResponse)
def export_tuning_tasks_csv(
    admin=Depends(require_admin),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
):
    """Export tuning tasks as CSV for the current tenant (for dashboard proxy)."""
    sb = get_supabase()
    tenant_id = admin.get("tenant_id") or "default"

    q = (
        sb.table("tuning_tasks")
        .select("id,created_at,task_type,severity,title,description,status,session_id")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .limit(500)
    )
    if status and status in VALID_STATUS:
        q = q.eq("status", status)
    if type and type in VALID_TYPE:
        q = q.eq("task_type", type)

    res = q.execute()
    rows: List[Dict[str, Any]] = res.data or []
    headers = ["id", "created_at", "task_type", "severity", "title", "description", "status", "session_id"]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(h, "") for h in headers])
    buf.seek(0)
    csv_content = buf.getvalue()

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="tuning-tasks-{tenant_id}.csv"',
        },
    )


@router.post("/from-session/{session_id}")
def create_tasks_from_session(session_id: str, admin=Depends(require_admin)):
    """
    Generate and create tuning tasks from a session.
    
    Analyzes the session and creates deterministic tuning tasks
    for missing keywords, specialty confusion, and weak questions.
    """
    sb = get_supabase()
    tenant_id = admin.get("tenant_id") or "default"

    # Fetch session (tenant-scoped)
    res = sb.table("triage_sessions").select("*").eq("id", session_id).eq("tenant_id", tenant_id).maybe_single().execute()
    session = res.data
    if not session:
        raise HTTPException(404, "Session not found")

    # Generate tasks
    tasks = build_tuning_tasks_from_session(session)
    if not tasks:
        return {"created": 0, "message": "No tuning tasks generated from this session"}

    # Insert tasks (tenant-scoped)
    created_count = 0
    for t in tasks:
        t["created_by"] = admin.get("user_id")
        t["tenant_id"] = tenant_id
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
    tenant_id = admin.get("tenant_id") or "default"

    # Fetch task (tenant-scoped)
    res = sb.table("tuning_tasks").select("*").eq("id", task_id).eq("tenant_id", tenant_id).maybe_single().execute()
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
    tenant_id = admin.get("tenant_id") or "default"

    # Update task status (tenant-scoped)
    res = sb.table("tuning_tasks").update({
        "status": "accepted",
        "applied_at": "now()",
        "applied_by": admin.get("user_id"),
    }).eq("id", task_id).eq("tenant_id", tenant_id).execute()
    
    if not res.data:
        raise HTTPException(404, "Task not found")
    
    return {
        "task_id": task_id,
        "status": "accepted",
        "message": "Patch marked as applied",
    }
