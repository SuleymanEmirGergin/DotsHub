"""Operator + super-admin endpoints over patient_uploads.

A1 lands the read surface (GET /v1/admin/uploads) — the operator
dashboard's review queue. A2 (review state PATCH) and A3 (lead-link
PATCH) extend this router.

Auth: ``require_admin_or_operator`` — both super-admin and any
operator role can READ the queue (filtering / triage). Write
endpoints (A2 + A3) layer ``require_min_role`` on top.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.admin_auth import require_admin_or_operator
from app.services import patient_uploads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/uploads", tags=["Admin Uploads"])


# Enum mirrors:
#   - ai_status from patient_uploads schema
#   - kind from patient_uploads.VALID_KINDS
# Pydantic Literal lets FastAPI 422 bad inputs at the route layer
# without us writing the validator.

AiStatusFilter = Literal["pending", "processing", "succeeded", "failed"]
KindFilter = Literal["image", "audio", "video", "document"]


class UploadListResponse(BaseModel):
    """Paginated review-queue response."""

    items: list[dict]
    total: int
    limit: int
    offset: int


@router.get("", response_model=UploadListResponse)
def list_uploads(
    ai_status: Optional[AiStatusFilter] = Query(default=None),
    kind: Optional[KindFilter] = Query(default=None),
    session_id: Optional[str] = Query(default=None, max_length=64),
    created_after: Optional[str] = Query(
        default=None, description="ISO 8601 timestamp; rows with created_at >= this"
    ),
    created_before: Optional[str] = Query(
        default=None, description="ISO 8601 timestamp; rows with created_at < this"
    ),
    include_tombstoned: bool = Query(
        default=False,
        description="Include rows that have been tombstoned (KVKK delete or retention sweep). Default off.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: dict = Depends(require_admin_or_operator),  # noqa: ARG001
):
    """Operator review queue. Filters compose with AND.

    Read access: any role (reviewer, manager, admin) AND super-admin.

    Tombstoned rows are hidden by default. ``include_tombstoned=true``
    surfaces them for forensic audit; the dashboard should never show
    tombstoned content to a regular reviewer (KVKK contract: deleted
    means deleted).
    """
    rows, total = patient_uploads.list_for_review(
        ai_status=ai_status,
        kind=kind,
        session_id=session_id,
        created_after=created_after,
        created_before=created_before,
        include_tombstoned=include_tombstoned,
        limit=limit,
        offset=offset,
    )
    # If supabase wrapped the response and the count came back None,
    # fall back to len(rows) as a soft signal -- pagination still
    # works on a single page.
    if total == 0 and rows:
        total = len(rows)
    return UploadListResponse(
        items=rows, total=total, limit=limit, offset=offset
    )
