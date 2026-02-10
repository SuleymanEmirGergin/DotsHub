"""Feedback endpoint — collects user rating on triage results.

POST /v1/triage/feedback
Stores feedback linked to a triage session for tuning & analytics.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import UUID

from app.supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request / Response Models ───

class FeedbackIn(BaseModel):
    session_id: UUID
    rating: Literal["up", "down"]
    comment: Optional[str] = Field(default=None, max_length=2000)
    user_selected_specialty_id: Optional[str] = Field(default=None, max_length=80)


class FeedbackOut(BaseModel):
    ok: bool = True


# ─── Route ───

@router.post("/triage/feedback", response_model=FeedbackOut)
def submit_feedback(payload: FeedbackIn):
    """Record user feedback on a triage result.

    Validates that the session exists before inserting feedback.
    This keeps the feedback data clean and traceable.
    """
    sb = get_supabase()

    # 1) Verify session exists
    session_resp = (
        sb.table("triage_sessions")
        .select("id")
        .eq("id", str(payload.session_id))
        .limit(1)
        .execute()
    )
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="session_id not found")

    # 2) Insert feedback
    insert_obj = {
        "session_id": str(payload.session_id),
        "rating": payload.rating,
        "comment": payload.comment,
        "user_selected_specialty_id": payload.user_selected_specialty_id,
    }
    ins = sb.table("triage_feedback").insert(insert_obj).execute()

    if ins.data is None:
        raise HTTPException(status_code=500, detail="failed to insert feedback")

    return FeedbackOut(ok=True)
