"""Explicit consent recording — KVKK Md.6(2) + GDPR Art.9(2)(a).

Compliance lineage: COMPLIANCE_CHECK_2026_04.md:KR-1.
Schema: backend/sql/20260427_consent_records.sql.
Privacy notice: docs/PRIVACY_NOTICE.md.

Endpoints:

  POST /v1/consent
      Record a grant or withdrawal. Append-only — every call is a new
      audit row. Returns the row id + server timestamp.

  GET  /v1/consent?device_id=...&consent_type=...
      Read the current state for a (device_id, consent_type) pair.
      Returns the latest row for that pair, or 404 if none exist.

Why no PUT/DELETE: KVKK Md.12 + GDPR Art.7(1) require the controller
to demonstrate that consent was given. Mutating or deleting prior
records would destroy that audit trail. Withdrawal is recorded as a
new row with `granted=false`.

Rate limiting: same bucket as feedback (60s / 20 req per IP). The
route handler does not apply this — it's enforced by the existing
`rate_limit_middleware` in main.py because the path matches /v1/.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.db import hash_ip

logger = logging.getLogger(__name__)

# Whitelist of consent types we accept. Adding a new type means:
#   1. Append it here
#   2. Add a corresponding CONSENT_VERSION_* in config.py
#   3. Update PRIVACY_NOTICE.md with the new clause
#   4. Bump PRIVACY_NOTICE_VERSION
ConsentType = Literal[
    "terms_general",
    "health_data_processing",
    "push_notifications",
    "summary_email",
]

_VALID_CONSENT_TYPES: set[str] = set(ConsentType.__args__)  # type: ignore[attr-defined]

router = APIRouter(prefix="/consent", tags=["Consent"])


class ConsentRecordRequest(BaseModel):
    consent_type: ConsentType
    consent_version: str = Field(..., min_length=1, max_length=32)
    granted: bool
    locale: str = Field(default="tr", max_length=10)
    device_id: Optional[str] = Field(default=None, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=64)
    notice_version: Optional[str] = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _require_identifier(self) -> "ConsentRecordRequest":
        if not self.device_id and not self.session_id:
            raise ValueError("device_id or session_id is required")
        return self


class ConsentRecordResponse(BaseModel):
    ok: bool = True
    id: Optional[int] = None
    granted_at: Optional[str] = None  # ISO-8601 from server


class ConsentStateResponse(BaseModel):
    granted: bool
    consent_version: str
    notice_version: Optional[str] = None
    locale: str
    granted_at: str  # ISO-8601


@router.post("", response_model=ConsentRecordResponse, status_code=201)
async def record_consent(
    body: ConsentRecordRequest, request: Request
) -> ConsentRecordResponse:
    """Insert a new consent audit row.

    Always inserts — never updates. The latest row by created_at for a
    given (device_id, consent_type) pair is the current state.
    """
    from app.db import supabase

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]

    row = {
        "device_id": body.device_id,
        "session_id": body.session_id,
        "consent_type": body.consent_type,
        "consent_version": body.consent_version,
        "granted": body.granted,
        "locale": body.locale,
        "notice_version": body.notice_version or settings.PRIVACY_NOTICE_VERSION,
        "ip_hash": hash_ip(client_ip),
        "user_agent": user_agent or None,
    }

    try:
        resp = (
            supabase.table("consent_records")
            .insert(row)
            .execute()
        )
    except Exception as exc:
        logger.error(
            "consent.persist_failed",
            extra={
                "consent_type": body.consent_type,
                "device_id": body.device_id,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CONSENT_PERSIST_FAILED",
                "message": "Consent could not be recorded; please retry",
            },
        ) from exc

    inserted = (resp.data or [{}])[0] if resp else {}
    logger.info(
        "consent.recorded",
        extra={
            "id": inserted.get("id"),
            "consent_type": body.consent_type,
            "consent_version": body.consent_version,
            "granted": body.granted,
            "locale": body.locale,
        },
    )
    return ConsentRecordResponse(
        ok=True,
        id=inserted.get("id"),
        granted_at=inserted.get("created_at"),
    )


@router.get("", response_model=ConsentStateResponse)
async def get_consent_state(
    device_id: str = Query(..., min_length=1, max_length=128),
    consent_type: str = Query(..., max_length=64),
) -> ConsentStateResponse:
    """Return the current consent state for a (device_id, consent_type).

    Latest-wins: a withdrawal AFTER a grant returns granted=false; a
    second grant after a withdrawal returns granted=true.
    """
    from app.db import supabase

    if consent_type not in _VALID_CONSENT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"unknown consent_type: {consent_type}"
        )

    try:
        resp = (
            supabase.table("consent_records")
            .select("granted,consent_version,notice_version,locale,created_at")
            .eq("device_id", device_id)
            .eq("consent_type", consent_type)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning(
            "consent.read_failed",
            extra={"consent_type": consent_type, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CONSENT_READ_FAILED",
                "message": "Consent state unavailable; please retry",
            },
        ) from exc

    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="no consent record")

    row = rows[0]
    return ConsentStateResponse(
        granted=bool(row["granted"]),
        consent_version=row["consent_version"],
        notice_version=row.get("notice_version"),
        locale=row.get("locale", "tr"),
        granted_at=row["created_at"],
    )
