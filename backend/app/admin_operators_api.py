"""Super-admin endpoints for managing dashboard operators.

All endpoints require ``x-admin-key`` (super-admin) — operator users
can NOT manage other operators (even with role=admin); the role
hierarchy in the operator_users table is for *resource* access (review
uploads, link leads), not for the operator-management surface itself.
This keeps the credential blast radius small: an operator key leak
can only do operator-level damage, never escalate to provisioning new
operators.

Rotation note: there is NO rotate-key endpoint in this surface yet.
A lost or compromised key is handled by deactivate + recreate (issue
a new operator with the same email; the email-live-uniq index allows
the reuse since the old row is tombstoned). Rotation is queued for a
later session if the operations cadence demands it.
"""
from __future__ import annotations

import logging
from typing import Optional

import re

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.admin_auth import require_admin_key
from app.services import operator_users

# Minimal email validator — full RFC 5322 is overkill for an internal
# operator surface. We don't add the email-validator dep just for this.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/operators", tags=["Admin Operators"])


def require_super_admin(x_admin_key: Optional[str] = Header(default=None)):
    return require_admin_key(x_admin_key)


# ─── Pydantic schemas ────────────────────────────────────────────────


class OperatorCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="reviewer")  # validated against VALID_ROLES below

    @field_validator("email")
    @classmethod
    def _check_email_shape(cls, v: str) -> str:
        if not _EMAIL_RE.match(v.strip()):
            raise ValueError("invalid email format")
        return v.strip().lower()


class OperatorCreateResponse(BaseModel):
    """Returned ONCE on create. ``api_key`` is the plaintext value the
    operator must save — it cannot be recovered later."""

    id: str
    email: str
    full_name: str
    role: str
    api_key: str  # plaintext, shown ONCE
    created_at: str


class OperatorRow(BaseModel):
    """Listing / get response shape — explicitly omits ``api_key`` /
    ``api_key_hash`` so the surface NEVER leaks credential material."""

    id: str
    email: str
    full_name: str
    role: str
    deactivated_at: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class OperatorUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[str] = None  # validated against VALID_ROLES below


# ─── Endpoints ───────────────────────────────────────────────────────


@router.post("", response_model=OperatorCreateResponse, status_code=201)
def create_operator(
    body: OperatorCreateRequest, _admin=Depends(require_super_admin),
):
    """Create a new operator. Returns the plaintext API key ONCE.

    422 on:
      - invalid role (not one of reviewer / manager / admin)
      - email collision with a LIVE operator (UNIQUE WHERE
        deactivated_at IS NULL); recreate is allowed only after
        deactivating the previous row
    """
    if not operator_users.is_valid_role(body.role):
        raise HTTPException(
            status_code=422,
            detail=(
                f"invalid role={body.role!r}; "
                f"valid: {sorted(operator_users.VALID_ROLES)}"
            ),
        )
    try:
        plain, row = operator_users.create(
            email=str(body.email),
            full_name=body.full_name,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        # Most likely the email-live-uniq index — surface as 409.
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"a live operator already exists with email "
                    f"{body.email!r}; deactivate first then recreate"
                ),
            ) from exc
        logger.error("operator_users.create_failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="operator creation failed"
        ) from exc

    return OperatorCreateResponse(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        api_key=plain,
        created_at=row["created_at"],
    )


@router.get("", response_model=list[OperatorRow])
def list_operators(
    include_deactivated: bool = False,
    _admin=Depends(require_super_admin),
):
    """List operators. ``include_deactivated=true`` surfaces tombstoned
    rows for forensic audit (which key authed which past action)."""
    rows = operator_users.list_all(include_deactivated=include_deactivated)
    return [OperatorRow(**r) for r in rows]


@router.patch("/{operator_id}", response_model=OperatorRow)
def update_operator(
    operator_id: str,
    body: OperatorUpdateRequest,
    _admin=Depends(require_super_admin),
):
    """Update name / role. Email is NOT updatable — recreate instead
    so the audit trail keeps the old email under the old hash.
    404 on unknown operator_id."""
    if body.role is not None and not operator_users.is_valid_role(body.role):
        raise HTTPException(
            status_code=422,
            detail=(
                f"invalid role={body.role!r}; "
                f"valid: {sorted(operator_users.VALID_ROLES)}"
            ),
        )
    if body.full_name is None and body.role is None:
        raise HTTPException(
            status_code=422,
            detail="at least one of full_name or role must be set",
        )
    row = operator_users.update(
        operator_id, full_name=body.full_name, role=body.role
    )
    if not row:
        raise HTTPException(status_code=404, detail="operator not found")
    return OperatorRow(**row)


@router.delete("/{operator_id}", status_code=204)
def deactivate_operator(
    operator_id: str, _admin=Depends(require_super_admin),
):
    """Soft-delete the operator. Idempotent — already-deactivated
    rows return 404 (caller can't tell the row "never existed" from
    "was already gone"; both are safe states)."""
    ok = operator_users.deactivate(operator_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="operator not found or already deactivated",
        )
    # 204: no body
