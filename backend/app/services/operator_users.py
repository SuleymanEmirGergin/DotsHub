"""Operator user service — per-user API keys for dashboard auth.

Bytes never leave RAM after key generation. The plaintext is returned
ONCE from ``create()`` and never persisted; only the SHA-256 hash
lands on the row. ``lookup_by_key`` re-hashes the incoming plaintext
and queries by the hash column — constant-time on the index lookup.

Design choices:
  - SHA-256 unsalted: collision attack against any one hash is
    infeasible (2^128 work for 50% probability), and we don't need
    rainbow-table protection because the input is already 32 random
    bytes (token_hex(32) = 64 hex chars = 256 bits of entropy).
  - 64-char hex (32 raw bytes): URL-safe, no padding, fits cleanly
    in an HTTP header value.
  - No bcrypt/scrypt: the input is already high-entropy, and we want
    sub-millisecond lookup on every authed request.
  - Email-uniqueness only among LIVE rows: re-hire / role-change use
    cases keep the email stable while the key history rotates.

Lifecycle:
    create() -> (plaintext_key, row)   shown once
    lookup_by_key(plaintext) -> row    every authed request
    list_all()                          dashboard list
    update(id, ...)                    rename / role change
    deactivate(id)                     soft delete; key stops working
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Roles ──────────────────────────────────────────────────────────


VALID_ROLES = frozenset({"reviewer", "manager", "admin"})

# Hierarchy used by ``require_min_role`` in admin_auth.py.
ROLE_RANK: dict[str, int] = {"reviewer": 1, "manager": 2, "admin": 3}


def is_valid_role(role: str) -> bool:
    return role in VALID_ROLES


# ─── Key generation + hashing ───────────────────────────────────────


def generate_api_key() -> tuple[str, str]:
    """Return ``(plaintext_key, sha256_hash)``.

    Plaintext is 64 hex chars (256 bits of entropy from
    ``secrets.token_hex(32)``). Hash is 64 hex chars from SHA-256 of
    the plaintext bytes (UTF-8 encoded). Caller persists the hash and
    surfaces the plaintext once.
    """
    plain = secrets.token_hex(32)
    hashed = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return plain, hashed


def hash_api_key(plain: str) -> str:
    """Hash the plaintext key the same way ``generate_api_key`` does.
    Used by ``lookup_by_key`` to translate an incoming header value
    into the column we index on."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


# ─── DB access ──────────────────────────────────────────────────────


def lookup_by_key(plain_key: str) -> Optional[dict]:
    """Look up a live operator by plaintext API key. Returns None on
    no match OR deactivated.

    Hashing happens in-process; only the hash hits Supabase. Even if
    DB query logging captured the value, the plaintext is never sent.
    """
    if not plain_key or len(plain_key) != 64:
        # Cheap reject for malformed headers — saves a DB round-trip.
        return None
    from app.db import supabase

    h = hash_api_key(plain_key)
    try:
        resp = (
            supabase.table("operator_users")
            .select(
                "id, email, full_name, role, deactivated_at, created_at"
            )
            .eq("api_key_hash", h)
            .is_("deactivated_at", "null")
            .maybe_single()
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("operator_users.lookup_failed: %s", exc)
        return None
    return resp.data if resp and resp.data else None


def create(*, email: str, full_name: str, role: str) -> tuple[str, dict]:
    """Insert a new operator and return ``(plaintext_key, row)``.

    The plaintext key MUST be displayed to the operator immediately;
    it cannot be recovered. The route handler is responsible for
    masking it in logs and surfacing it exactly once in the response.
    """
    if not is_valid_role(role):
        raise ValueError(f"invalid role={role!r}; valid: {sorted(VALID_ROLES)}")
    if not email or not full_name:
        raise ValueError("email and full_name are required")

    from app.db import supabase

    plain, h = generate_api_key()
    row_in = {
        "email": email.strip().lower(),
        "full_name": full_name.strip(),
        "role": role,
        "api_key_hash": h,
    }
    resp = supabase.table("operator_users").insert(row_in).execute()
    if not resp.data:
        raise RuntimeError("operator_users insert returned no row")
    return plain, resp.data[0]


def list_all(*, include_deactivated: bool = False) -> list[dict]:
    """List operators, sorted newest first. ``api_key_hash`` is
    deliberately omitted from the projection — the dashboard never
    needs it and surfacing it would defeat the hash-only design."""
    from app.db import supabase

    q = (
        supabase.table("operator_users")
        .select(
            "id, email, full_name, role, deactivated_at, created_at, updated_at"
        )
        .order("created_at", desc=True)
    )
    if not include_deactivated:
        q = q.is_("deactivated_at", "null")
    try:
        resp = q.execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("operator_users.list_failed: %s", exc)
        return []
    return resp.data or []


def get_by_id(operator_id: str) -> Optional[dict]:
    from app.db import supabase

    try:
        resp = (
            supabase.table("operator_users")
            .select(
                "id, email, full_name, role, deactivated_at, created_at, updated_at"
            )
            .eq("id", operator_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("operator_users.get_failed id=%s: %s", operator_id, exc)
        return None
    return resp.data if resp and resp.data else None


def update(
    operator_id: str,
    *,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
) -> Optional[dict]:
    """Update name / role. Returns the updated row, or None if no
    matching row. Email is NOT updatable — re-create instead so the
    audit trail stays clean (`history of operator under email X`)."""
    if role is not None and not is_valid_role(role):
        raise ValueError(f"invalid role={role!r}; valid: {sorted(VALID_ROLES)}")

    patch: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if full_name is not None:
        patch["full_name"] = full_name.strip()
    if role is not None:
        patch["role"] = role

    from app.db import supabase

    try:
        resp = (
            supabase.table("operator_users")
            .update(patch)
            .eq("id", operator_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("operator_users.update_failed id=%s: %s", operator_id, exc)
        return None
    if not resp.data:
        return None
    return resp.data[0]


def deactivate(operator_id: str) -> bool:
    """Soft-delete the operator. Subsequent lookups by the operator's
    key return None. Returns True on success, False if the row didn't
    exist or was already deactivated.

    Hash is preserved on the row for forensic audit ("which key
    authed this action?"). Recreating with the same email + role is
    fine — the email-live-uniq index excludes deactivated rows.
    """
    from app.db import supabase

    now = datetime.now(timezone.utc).isoformat()
    try:
        resp = (
            supabase.table("operator_users")
            .update({"deactivated_at": now, "updated_at": now})
            .eq("id", operator_id)
            .is_("deactivated_at", "null")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "operator_users.deactivate_failed id=%s: %s", operator_id, exc
        )
        return False
    return bool(resp.data)
