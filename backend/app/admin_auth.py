"""Shared admin authentication helpers.

Two auth tiers:
  1. **Super-admin** — ``x-admin-key`` header matching
     ``settings.ADMIN_API_KEY`` (single env-configured secret).
     Always passes role checks. The legacy ``require_admin_key``
     entry-point is preserved for endpoints that don't yet recognise
     operator users.
  2. **Operator** — ``x-operator-key`` header looked up against
     ``operator_users.api_key_hash`` (see services/operator_users.py).
     Carries one of three roles enforced by ``require_min_role``.

New code should prefer ``require_admin_or_operator`` so the same
endpoint accepts both tiers; the role check (``require_min_role``)
runs at the route handler level rather than in the dependency so a
single dependency can serve multiple endpoints with different role
floors.
"""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings
from app.services import operator_users


# ─── Role hierarchy ────────────────────────────────────────────────


# Mirrors operator_users.ROLE_RANK; re-exported here so route handlers
# don't need to import the service module just to call require_min_role.
ROLE_RANK: dict[str, int] = {"reviewer": 1, "manager": 2, "admin": 3}


# ─── Legacy super-admin only ────────────────────────────────────────


def require_admin_key(x_admin_key: str | None) -> dict[str, str]:
    """Validate x-admin-key against ADMIN_API_KEY.

    Preserved for endpoints that haven't migrated to
    ``require_admin_or_operator``; new code should use the latter.
    """
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured")

    if not x_admin_key or not hmac.compare_digest(
        x_admin_key, settings.ADMIN_API_KEY
    ):
        raise HTTPException(status_code=401, detail="unauthorized")

    return {"user_id": "admin_api_key"}


# ─── Combined admin OR operator ─────────────────────────────────────


def require_admin_or_operator(
    x_admin_key: Optional[str] = Header(default=None),
    x_operator_key: Optional[str] = Header(default=None),
) -> dict:
    """Accept either super-admin or operator credentials.

    Returns a normalised auth context dict:
        {
          "id": str,            # "admin_api_key" or operator UUID
          "name": str,          # display name for audit columns
          "role": str,          # "admin" for super-admin; operator's role
          "is_super_admin": bool,
          "email": Optional[str],  # operator's email when applicable
        }

    401 paths:
      - Both headers missing (or both invalid)
      - x-operator-key set but the row was deactivated / unknown
    """
    # Prefer x-admin-key when set AND valid. Falling back to operator
    # key on a wrong x-admin-key is a deliberate convenience: an
    # operator-key-holder can leave x-admin-key unset and the system
    # still works.
    if x_admin_key and settings.ADMIN_API_KEY and hmac.compare_digest(
        x_admin_key, settings.ADMIN_API_KEY
    ):
        return {
            "id": "admin_api_key",
            "name": "admin",
            "role": "admin",
            "is_super_admin": True,
            "email": None,
        }

    if not x_operator_key:
        raise HTTPException(
            status_code=401,
            detail="missing x-admin-key or x-operator-key",
        )

    op = operator_users.lookup_by_key(x_operator_key)
    if not op:
        # Same 401 message regardless of "unknown" vs "deactivated" so
        # callers can't distinguish (auth-enumeration mitigation).
        raise HTTPException(
            status_code=401, detail="unknown or deactivated operator key"
        )

    # Per-operator rate limit. Runs AFTER the auth lookup so an unknown
    # key 401s before counting against any bucket. Super-admin skips
    # this path; the existing admin-rate-limit middleware (IP-keyed)
    # already gates super-admin requests.
    from app.rate_limit import build_operator_rl_key, check_operator_rate_limit
    rl_key = build_operator_rl_key(op["id"])
    allowed, remaining, reset_in = check_operator_rate_limit(rl_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"operator rate limit exceeded; retry in {reset_in}s"
            ),
            headers={"Retry-After": str(reset_in)},
        )

    return {
        "id": op["id"],
        "name": op.get("full_name") or op.get("email") or "operator",
        "role": op.get("role", "reviewer"),
        "is_super_admin": False,
        "email": op.get("email"),
    }


def require_min_role(auth: dict, min_role: str) -> None:
    """Raise 403 unless ``auth.role`` meets ``min_role`` in the
    hierarchy. Super-admin always passes.

    Designed to be called at the top of a route handler:

        def my_endpoint(auth=Depends(require_admin_or_operator)):
            require_min_role(auth, "manager")
            ...
    """
    if auth.get("is_super_admin"):
        return
    op_role = auth.get("role", "reviewer")
    if ROLE_RANK.get(op_role, 0) < ROLE_RANK.get(min_role, 0):
        raise HTTPException(
            status_code=403,
            detail=(
                f"requires role>={min_role}; current role={op_role}"
            ),
        )
