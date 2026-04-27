"""KVKK / GDPR data rights endpoints.

User-facing (not admin): deletes one triage session OR one
health-tourism lead and all of its derived rows. The row itself is
replaced with a tombstone — we keep the ID + deletion timestamp so
analytics totals don't silently drop and so we can honor
cross-reference audits ("was this session ever here?"). For
health-tourism leads, the regulator (Sağlık Turizmi Yönetmeliği
Madde 10) requires 5-year retention, so the tombstone is mandatory.

Endpoints:
    DELETE /v1/me/sessions/{session_id}   — triage data wipe
    DELETE /v1/me/leads/{lead_id}         — health-tourism lead wipe

Contract:
    - Public (no admin_key required) because the user is exercising
      their own rights. Authentication is via possession of the
      session_id / lead_id — both are unguessable UUIDs and only the
      mobile app holds them.
    - Idempotent: deleting an already-tombstoned record is a
      200-no-op.
    - Returns a short receipt with what was deleted.

What gets wiped:
    triage_events           DELETE WHERE session_id = X
    llm_calls               DELETE WHERE session_id = X
    triage_feedback         DELETE WHERE session_id = X
    triage_sessions         UPDATE SET input_text=NULL,
                                      answers=NULL,
                                      user_canonicals_tr=NULL,
                                      top_conditions=NULL,
                                      doctor_ready_summary_tr=NULL,
                                      meta=NULL,
                                      deleted_at=NOW(),
                                      deleted_reason='user_request'

Why tombstone not full-row DELETE on triage_sessions:
    - Analytics dashboards join on session_id from feedback / events
      after-the-fact; a missing session breaks those joins silently.
    - The row keeps shape but carries no user-identifiable content.
    - 90-day retention policy can still purge tombstones on schedule.

Rate limit: same as feedback (see main.py rate_limit_middleware) —
we don't want this endpoint weaponized to delete other users'
sessions by brute-forcing UUIDs, but UUIDs are 128-bit random so
brute-force is infeasible in practice anyway.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

# NOTE: `from app.db import supabase` is intentionally NOT at module
# level. app.db raises RuntimeError at import time if SUPABASE_URL /
# SUPABASE_SERVICE_ROLE_KEY are missing, which would break every CI
# test that imports app.main (even ones that don't touch this route).
# Each handler below imports supabase lazily, the same pattern
# admin_tenants_api._write_audit_row uses.

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["Data Rights"])


@router.delete("/sessions/{session_id}")
def delete_my_session(session_id: str) -> Dict[str, Any]:
    """Tombstone one triage session + wipe its derived rows."""
    from app.db import supabase

    # Quick shape check — UUID-ish. supabase would 400 on malformed
    # anyway but we catch early for a nicer error.
    if len(session_id) < 32 or len(session_id) > 40:
        raise HTTPException(status_code=400, detail="malformed session_id")

    # Confirm the session exists (else 404 so the user gets a
    # meaningful response).
    existing = (
        supabase.table("triage_sessions")
        .select("id,deleted_at")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    if not existing or not existing.data:
        raise HTTPException(status_code=404, detail="session not found")

    if existing.data.get("deleted_at"):
        # Idempotent: already tombstoned. Return a no-op receipt.
        return {
            "ok": True,
            "session_id": session_id,
            "already_deleted": True,
        }

    deleted_counts: Dict[str, int] = {}

    # Derived tables — delete fully. Missing columns are tolerated
    # silently by supabase-py, so each delete is independent.
    for table in ("triage_events", "llm_calls", "triage_feedback"):
        try:
            resp = (
                supabase.table(table).delete().eq("session_id", session_id).execute()
            )
            deleted_counts[table] = len(resp.data or []) if resp else 0
        except Exception as exc:
            logger.warning("data_rights: delete from %s failed: %s", table, exc)
            deleted_counts[table] = -1  # signal "attempted, failed"

    # patient_uploads: tombstone (NOT delete) — the schema's
    # ON DELETE SET NULL would orphan the row's audit trail, and
    # KVKK contract is "content gone, ID kept for cross-reference".
    # The tombstone helper handles idempotency (skips already-
    # tombstoned rows) so calling on a re-deletion is a no-op.
    from app.services.patient_uploads import tombstone_uploads_for_session
    deleted_counts["patient_uploads"] = tombstone_uploads_for_session(
        session_id, reason="user_request"
    )

    # Tombstone the session row. Clear all content columns we might
    # conceivably hold PII in; keep id + timestamps + deletion
    # metadata for referential integrity with any remaining joins.
    from datetime import datetime, timezone

    try:
        supabase.table("triage_sessions").update(
            {
                "input_text": None,
                "answers": None,
                "user_canonicals_tr": None,
                "asked_canonicals": None,
                "top_conditions": None,
                "doctor_ready_summary_tr": None,
                "why_specialty_tr": None,
                "specialty_scoring_debug": None,
                "confidence_debug": None,
                "emergency_reason_tr": None,
                "meta": None,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deleted_reason": "user_request",
            }
        ).eq("id", session_id).execute()
    except Exception as exc:
        logger.error("data_rights: tombstone failed for %s: %s", session_id, exc)
        raise HTTPException(
            status_code=500, detail="tombstone failed; try again"
        ) from exc

    logger.info(
        "data_rights: session %s tombstoned; derived deletes: %s",
        session_id,
        deleted_counts,
    )
    return {
        "ok": True,
        "session_id": session_id,
        "derived_deleted": deleted_counts,
    }


# ──────────────────────────────────────────────────────────
# DELETE /v1/me/leads/{lead_id}  — health-tourism lead silme
# ──────────────────────────────────────────────────────────
#
# Why a separate endpoint from /sessions:
#   - Different table, different schema, different retention rule.
#   - The session tombstone clears triage payloads; the lead
#     tombstone clears contact PII while preserving the row for the
#     5-year retention requirement (Sağlık Turizmi Yönetmeliği
#     Madde 10). Operators must be able to prove "we received this
#     lead and handled it" if questioned by the regulator — the
#     tombstone keeps that audit trail intact.
#   - Reusing /sessions/{id} would be wrong both semantically (lead
#     IDs are not session IDs) and operationally (different
#     deletion semantics per regulator).


@router.delete("/leads/{lead_id}")
def delete_my_lead(lead_id: str) -> Dict[str, Any]:
    """KVKK silme: tombstone one health-tourism lead.

    Soft-delete via lead_repository.soft_delete():
        - is_deleted = true
        - contact JSONB nulled
        - notes cleared
        - deleted_at stamped
        - row preserved for 5-year retention

    Returns:
        - 200 with `ok: true` on success (or already-deleted no-op)
        - 404 when the lead_id doesn't exist
        - 500 when Supabase is unreachable

    Authentication is by possession of the unguessable lead_id —
    same model as the session endpoint above. No admin_key.
    """
    from app.services import lead_repository

    if len(lead_id) < 32 or len(lead_id) > 40:
        raise HTTPException(status_code=400, detail="malformed lead_id")

    # Idempotent: if the row is already deleted, return a no-op
    # success rather than 404, so retries don't surprise the caller.
    existing = lead_repository.get(lead_id)
    if existing is None:
        # Could be 'never existed' OR 'Supabase unreachable'.
        # Distinguish only via Supabase env probe — the get() helper
        # already returned None for both. Treat as 404 to match the
        # session endpoint's behaviour: an unfindable record is a
        # not-found from the user's perspective.
        raise HTTPException(status_code=404, detail="lead not found")
    if existing.get("is_deleted"):
        return {
            "ok": True,
            "lead_id": lead_id,
            "already_deleted": True,
        }

    success = lead_repository.soft_delete(lead_id)
    if not success:
        # The get() above succeeded so the row exists — a False here
        # means Supabase failed on the update path (transient). Tell
        # the user to retry rather than silently 200'ing.
        raise HTTPException(
            status_code=500, detail="lead deletion failed; try again"
        )

    logger.info("data_rights: lead %s tombstoned (KVKK silme)", lead_id)
    return {
        "ok": True,
        "lead_id": lead_id,
        "tombstoned": True,
    }
