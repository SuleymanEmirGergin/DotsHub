"""KVKK / GDPR data rights endpoint.

User-facing (not admin): deletes one triage session and all of its
derived rows (events, LLM calls, feedback). The session row itself
is replaced with a tombstone — we keep the ID + deletion timestamp
so analytics totals don't silently drop and so we can honor
cross-reference audits ("was this session ever here?").

Endpoint:
    DELETE /v1/me/sessions/{session_id}

Contract:
    - Public (no admin_key required) because the user is exercising
      their own rights. Authentication is via possession of the
      session_id — triage sessions are unguessable UUIDs and the
      mobile app is the only thing that holds them.
    - Idempotent: deleting an already-tombstoned session is a
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

    # WORM audit trail (DPIA R-10) — best-effort; never raises.
    # Records WHO erased WHAT and WHEN, with derived-delete counts as
    # forensic context. The actor_id is the session_id itself
    # (possession-as-auth model — session_ids are unguessable UUIDs
    # the mobile app holds), since data_rights is the user-facing
    # erasure path with no separate device_id on the request.
    from app.audit import record_event

    record_event(
        event_type="data_rights.session_tombstoned",
        actor_type="user",
        actor_id=session_id,
        target_id=session_id,
        severity="info",
        payload={
            "deleted_reason": "user_request",
            "derived_deleted": deleted_counts,
        },
    )

    return {
        "ok": True,
        "session_id": session_id,
        "derived_deleted": deleted_counts,
    }
