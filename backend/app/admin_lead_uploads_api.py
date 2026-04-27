"""PATCH /v1/admin/leads/{lead_id}/uploads — operator links uploads to a lead.

Replace semantics: send the desired full set; the service computes
the diff and applies the minimum set of writes (add new, tombstone
removed, leave unchanged ones alone).

Auth: super-admin OR operator with role >= manager. Reviewer-tier
operators can review individual uploads (A2) but can't curate the
lead-level link bag — that's a managerial action that affects how
the lead surfaces in the operator's lead-detail view.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.admin_auth import require_admin_or_operator, require_min_role
from app.services import lead_uploads, patient_uploads

logger = logging.getLogger(__name__)

# NOTE: prefix /admin/leads (not /admin/uploads) — different resource
# tree. Living in its own router keeps the route file focused.
router = APIRouter(prefix="/admin/leads", tags=["Admin Lead Uploads"])


class LinkUploadsRequest(BaseModel):
    """Replace the full set of uploads linked to this lead.

    Empty list = unlink all (every current link gets tombstoned).
    Cap at 100 keeps a runaway client from constructing pathological
    payloads; in practice operators link ~3-10 uploads per lead.
    """

    asset_ids: list[str] = Field(default_factory=list, max_length=100)


class LinkUploadsResponse(BaseModel):
    """Diff summary so the dashboard can render "you added X, removed Y"."""

    added: list[str]
    removed: list[str]
    kept: list[str]
    current: list[str]


def _resolve_linker(auth: dict) -> str:
    """Same convention as patient_uploads.reviewed_by: super-admin
    -> "admin"; operator -> email (preferred) / name / id."""
    if auth.get("is_super_admin"):
        return "admin"
    return (
        auth.get("email")
        or auth.get("name")
        or auth.get("id")
        or "operator"
    )


@router.patch("/{lead_id}/uploads", response_model=LinkUploadsResponse)
def link_uploads_to_lead(
    lead_id: str,
    body: LinkUploadsRequest,
    auth: dict = Depends(require_admin_or_operator),
):
    """Set the lead's upload links to exactly ``body.asset_ids``.

    Status codes:
      - 200: diff applied, returns {added, removed, kept, current}
      - 401: missing / unknown auth
      - 403: operator below manager
      - 404: lead doesn't exist
      - 422: at least one asset_id is unknown OR tombstoned
        (atomic precheck — no partial diff applied)
    """
    require_min_role(auth, "manager")

    if not lead_uploads.lead_exists(lead_id):
        raise HTTPException(status_code=404, detail="lead not found")

    # Precheck every asset before touching anything. Atomic-ish: a
    # later tombstone landing between this loop and the diff write is
    # a tiny race window; the unique partial index on lead_uploads
    # would catch a tombstoned-then-relinked attempt anyway.
    invalid: list[str] = []
    for aid in body.asset_ids:
        if patient_uploads.get_upload(aid) is None:
            invalid.append(aid)
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=(
                f"unknown or tombstoned asset_ids: {invalid}. "
                "No links were modified."
            ),
        )

    diff = lead_uploads.replace_links_for_lead(
        lead_id,
        body.asset_ids,
        linked_by_operator_id=_resolve_linker(auth),
    )
    return LinkUploadsResponse(**diff)


@router.get("/{lead_id}/uploads", response_model=list[dict])
def get_lead_links(
    lead_id: str, auth: dict = Depends(require_admin_or_operator),  # noqa: ARG001
):
    """Read-side companion: list the live links for a lead.

    Auth: any role >= reviewer (read access). Returns the link rows
    (NOT the full upload metadata — fetch those via
    GET /v1/admin/uploads with session_id filter or per-asset).
    """
    if not lead_uploads.lead_exists(lead_id):
        raise HTTPException(status_code=404, detail="lead not found")
    return lead_uploads.list_active_for_lead(lead_id)
