"""Session CRUD helpers — Supabase upsert + event log.

Every turn:
  - session yoksa → create
  - varsa → update (patch)
  - Her envelope → triage_events'e event yaz
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import UUID

from app.supabase_client import get_supabase


def create_session(
    locale: str,
    input_text: str,
    device_id: Optional[str] = None,
) -> UUID:
    """Create a new triage session and return its UUID.

    ``device_id`` is the stable per-install identifier sent by the mobile
    client (also persisted in push_tokens). Storing it on the session row
    enables follow-up reminder pushes — we join sessions → push_tokens
    by device_id and target only sessions that originated from a device
    we know how to notify.
    """
    sb = get_supabase()
    row: Dict[str, Any] = {
        "locale": locale,
        "input_text": input_text,
        "envelope_type": "QUESTION",
        "turn_index": 0,
    }
    if device_id:
        # Backend-side trim + length cap as defense-in-depth; Pydantic
        # already enforces max_length=128 at the route boundary.
        row["device_id"] = device_id.strip()[:128]
    ins = sb.table("triage_sessions").insert(row).execute()

    if not ins.data:
        raise RuntimeError("Failed to create session")
    return UUID(ins.data[0]["id"])


def update_session(session_id: UUID, patch: Dict[str, Any]) -> None:
    """Patch an existing triage session."""
    sb = get_supabase()
    upd = (
        sb.table("triage_sessions")
        .update(patch)
        .eq("id", str(session_id))
        .execute()
    )
    if upd.data is None:
        raise RuntimeError("Failed to update session")


def append_event(
    session_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Write a row to triage_events (immutable log)."""
    sb = get_supabase()
    sb.table("triage_events").insert({
        "session_id": str(session_id),
        "event_type": event_type,
        "payload": payload,
    }).execute()


def get_session(session_id: UUID) -> Optional[Dict[str, Any]]:
    """Load a session by id. Returns None if not found."""
    sb = get_supabase()
    res = (
        sb.table("triage_sessions")
        .select("*")
        .eq("id", str(session_id))
        .single()
        .execute()
    )
    return res.data if res and res.data else None
