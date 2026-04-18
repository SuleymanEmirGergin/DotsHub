"""Admin feedback acknowledge flow.

Lets admins mark a triage_feedback row as seen+actioned with an
optional note (typically a PR link or "added synonym X"). The read
side lives in the dashboard feedback page; this module only exposes
the write endpoint.

Endpoint:
    POST /v1/admin/feedback/{feedback_id}/ack
    Body: {"ack_note": "optional free text"}
    Auth: x-admin-key

Behaviour:
    - Requires feedback_id to exist; else 404.
    - Idempotent: re-acking updates acknowledged_at / actor / note.
    - Returns the updated row so the dashboard can re-render without
      a separate fetch.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.admin_auth import require_admin_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/feedback", tags=["Admin Feedback"])


def require_admin(x_admin_key: str | None = Header(default=None)):
    return require_admin_key(x_admin_key)


class AckRequest(BaseModel):
    ack_note: Optional[str] = Field(default=None, max_length=500)


@router.post("/{feedback_id}/ack")
def ack_feedback(
    feedback_id: str,
    req: AckRequest,
    admin=Depends(require_admin),
) -> Dict[str, Any]:
    """Mark a feedback row as acknowledged."""
    from app.db import supabase

    actor = admin.get("user_id") if isinstance(admin, dict) else None
    now_iso = datetime.now(timezone.utc).isoformat()

    # Verify the row exists first — Supabase .update() silently
    # succeeds even when nothing matches, so a bogus id would pass
    # without our 404.
    existing = (
        supabase.table("triage_feedback")
        .select("id")
        .eq("id", feedback_id)
        .maybe_single()
        .execute()
    )
    if not existing or not existing.data:
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id!r} not found")

    try:
        resp = (
            supabase.table("triage_feedback")
            .update(
                {
                    "acknowledged_at": now_iso,
                    "acknowledged_by": actor,
                    "ack_note": req.ack_note,
                }
            )
            .eq("id", feedback_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Feedback ack failed for %s: %s", feedback_id, exc)
        raise HTTPException(status_code=500, detail="ack failed") from exc

    logger.info(
        "Feedback %s acknowledged by %r (note=%s)",
        feedback_id,
        actor,
        bool(req.ack_note),
    )
    updated = resp.data[0] if resp and getattr(resp, "data", None) else None
    return {"ok": True, "feedback": updated}
