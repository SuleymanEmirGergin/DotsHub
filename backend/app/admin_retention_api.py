"""Operator-only retention sweep endpoints.

POST /v1/admin/retention/patient-uploads/sweep — tombstones every
patient_uploads row whose ``expires_at`` is in the past. Designed to
be called by a nightly GitHub Actions cron
(``.github/workflows/patient-uploads-retention.yml``); the auth gate
is the standard ``x-admin-key`` header.

Why an HTTP endpoint vs. a standalone script:
  - The cron workflow already has the auth + curl pattern
    (see health-alert.yml). One HTTP entry-point per recurring task
    keeps deployment surface minimal — we don't have a separate
    long-running scheduler container, just `curl + admin key`.
  - Tests can hit the endpoint via TestClient without a script
    runner / subprocess dance.

Patient impact when sweep runs: zero — tombstone is a soft delete
that NULLs PII columns but keeps the row id for cross-reference. The
GET /v1/patient/upload/{asset_id} polling endpoint already treats
tombstoned rows as 404 (KVKK indistinguishability).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from app.admin_auth import require_admin_key
from app.services import patient_uploads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/retention", tags=["Admin Retention"])


def require_admin(x_admin_key: str | None = Header(default=None)):
    return require_admin_key(x_admin_key)


@router.post("/patient-uploads/sweep")
def sweep_patient_uploads(admin=Depends(require_admin)):  # noqa: ARG001
    """Tombstone expired patient_uploads rows.

    Returns ``{tombstoned_count, processed_at}``. The cron worker
    expects a 200 with the count; -1 from the service signals a DB
    error and surfaces as a 500 here so the workflow flags + alerts.
    """
    started = datetime.now(timezone.utc).isoformat()
    count = patient_uploads.tombstone_expired_uploads(
        reason="scheduled_retention"
    )
    if count < 0:
        # Service returns -1 on DB blip. Surface as 500 so the cron
        # workflow re-tries on the next run and the alert fires.
        raise HTTPException(
            status_code=500,
            detail="retention sweep failed; see backend logs",
        )
    return {
        "tombstoned_count": count,
        "started_at": started,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
