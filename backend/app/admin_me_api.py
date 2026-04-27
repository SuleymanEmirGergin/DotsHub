"""GET /v1/admin/me — auth context echo for dashboard role gating.

The dashboard pages need to know the current user's role + identity
to gate UI (e.g. only show "+ Yeni operatör" button to super-admin,
hide the lead-link curate buttons from reviewer-tier operators).

This endpoint surfaces the dict that ``require_admin_or_operator``
already builds, with one tweak: never echo the raw ``id`` for
super-admin sessions (it's the literal "admin_api_key" string, not a
real id; misleading at the call site). Operators get their UUID id
because role-change events on the dashboard need to look the row up.

Auth: any tier — super-admin OR any operator role. The endpoint is
itself the role-discovery surface, so role gating happens AFTER
the response.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.admin_auth import require_admin_or_operator

router = APIRouter(prefix="/admin/me", tags=["Admin Me"])


@router.get("")
def get_me(auth: dict = Depends(require_admin_or_operator)):
    """Return the caller's auth context.

    Response shape:
        {
          "id": str,                # operator UUID OR "admin_api_key"
          "name": str,              # display name for UI greetings
          "role": str,              # "reviewer" | "manager" | "admin"
          "is_super_admin": bool,   # true when authed via ADMIN_API_KEY
          "email": str | null,      # operator email; null for super-admin
        }

    Dashboard caches this response for the session and gates UI
    accordingly. Backend role enforcement is the actual gate; this
    endpoint is purely a UX hint.
    """
    # require_admin_or_operator already returns the normalised shape;
    # we re-emit it as-is. No additional fields ever — the dict shape
    # is part of the contract documented on the dashboard side.
    return {
        "id": auth.get("id"),
        "name": auth.get("name"),
        "role": auth.get("role"),
        "is_super_admin": bool(auth.get("is_super_admin")),
        "email": auth.get("email"),
    }
